"""Escalate city-assigned demonstrations to the national team after 24 h.

Runs as a background job (see ``background_jobs/definitions.py``): leadership-
coordinated across gunicorn workers, so exactly one escalation sweep runs at a
time. Demonstrations assigned to city admins that have not been acted on within
``CITY_ASSIGNMENT_ESCALATION_HOURS`` (default 24) are emailed to the national
team and flipped to ``city_assignment.escalated = true`` so they re-enter the
national pending queue and reminder loop.

A demonstration is only marked escalated after the notification email has been
sent successfully, so a temporary SMTP failure retries the escalation on the
next run instead of losing the outage silently.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.emailer.EmailJob import EmailJob
from mielenosoitukset_fi.emailer.EmailSender import EmailSender
from mielenosoitukset_fi.utils.city_assignment import (
    DEFAULT_ESCALATION_HOURS,
    escalate_overdue,
    mark_escalated,
)
from mielenosoitukset_fi.utils.logger import logger
from mielenosoitukset_fi.utils.time_utils import utcnow
from mielenosoitukset_fi.admin.admin_demo_bp import (
    generate_demo_approve_link,
    generate_demo_preview_link,
    generate_demo_reject_link,
)

ASSIGNMENT_TEMPLATE = "admin_demo_city_escalation.html"
ADMIN_RECIPIENTS = ["tuki@mielenosoitukset.fi"]


def _submitter_context(db, demo_id) -> Dict[str, Optional[str]]:
    submitter = db.submitters.find_one({"demonstration_id": demo_id}) or {}
    return {
        "submitter_name": submitter.get("submitter_name"),
        "submitter_email": submitter.get("submitter_email"),
        "submitter_role": submitter.get("submitter_role"),
    }


def _queue_escalation_email(
    email_sender: EmailSender,
    db,
    demo: Dict[str, Any],
    escalate_after_hours: int,
) -> bool:
    demo_id = demo["_id"]
    try:
        approve_link = generate_demo_approve_link(str(demo_id))
        preview_link = generate_demo_preview_link(str(demo_id))
        reject_link = generate_demo_reject_link(str(demo_id))
    except Exception:
        logger.exception("Failed to generate escalation links for demo %s", demo_id)
        return False

    context = {
        "title": demo.get("title"),
        "date": demo.get("date"),
        "city": demo.get("city"),
        "address": demo.get("address"),
        "escalate_after_hours": escalate_after_hours,
        "approve_link": approve_link,
        "preview_link": preview_link,
        "reject_link": reject_link,
        **_submitter_context(db, demo_id),
    }

    try:
        rendered_body = email_sender._env.get_template(ASSIGNMENT_TEMPLATE).render(context)
    except Exception:
        logger.exception("Failed to render escalation email for demo %s", demo_id)
        return False

    job = EmailJob(
        subject=f"Eskaloitu: {context['title'] or 'mielenosoitus'} odottaa edelleen hyväksyntää ({context['city']})",
        recipients=ADMIN_RECIPIENTS,
        body=rendered_body,
        html=rendered_body,
        instance_id=email_sender._instance_id,
    )
    try:
        email_sender.send_email(job, raise_on_error=True)
    except Exception:
        logger.exception("Failed to send escalation email for demo %s", demo_id)
        return False
    return True


def escalate_once(
    db=None,
    email_sender: Optional[EmailSender] = None,
    *,
    escalate_after_hours: Optional[int] = None,
    max_to_process: int = 50,
) -> int:
    """Escalate overdue city-assigned demos to the national team."""
    try:
        from config import Config
    except Exception:  # pragma: no cover - defensive fallback
        Config = None

    if escalate_after_hours is None:
        escalate_after_hours = int(
            getattr(Config, "CITY_ASSIGNMENT_ESCALATION_HOURS", DEFAULT_ESCALATION_HOURS)
            or DEFAULT_ESCALATION_HOURS
        )
    db = db if db is not None else DatabaseManager().get_instance().get_db()
    email_sender = email_sender if email_sender is not None else EmailSender()

    escalated = 0
    for demo in escalate_overdue(
        db,
        escalate_after_hours=escalate_after_hours,
        max_to_process=max_to_process,
    ):
        if _queue_escalation_email(email_sender, db, demo, escalate_after_hours):
            if mark_escalated(db, demo["_id"], notified=True):
                escalated += 1
                logger.info("Escalated demo %s to the national team.", demo["_id"])

    if escalated:
        logger.info("Escalated %d city-assigned demo(s) to the national team.", escalated)
    return escalated


def main() -> Dict[str, int]:
    """Background job entry point (see background_jobs/definitions.py)."""
    escalated = escalate_once()
    return {"escalated": escalated}