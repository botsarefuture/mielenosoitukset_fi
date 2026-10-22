from __future__ import annotations

from mielenosoitukset_fi.utils.time_utils import utcnow
from datetime import datetime, timedelta
from typing import Any, Dict, List
from uuid import uuid4
import smtplib

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, ReturnDocument

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.emailer.EmailJob import EmailJob
from mielenosoitukset_fi.emailer.EmailSender import EmailSender
from mielenosoitukset_fi.utils.logger import logger
from mielenosoitukset_fi.utils.city_assignment import (
    NOT_ESCALATED_ASSIGNMENT_CLAUSE,
    active_city_admins_for_city,
    has_live_assignment,
)
from mielenosoitukset_fi.admin.admin_demo_bp import (
    generate_demo_approve_link,
    generate_demo_preview_link,
    generate_demo_reject_link,
)
from mielenosoitukset_fi.scripts.merge_duplicate_submissions import (
    merge_duplicate_submissions,
)

email_sender = EmailSender()
ADMIN_RECIPIENTS = ["tuki@mielenosoitukset.fi"]
MAX_ATTEMPTS = 5
STALE_AFTER = timedelta(minutes=10)


class ClaimLost(RuntimeError):
    """The worker no longer owns this job; do not acknowledge or send more."""


def _owned_update(queue, owner, update):
    if not queue.update_one(owner, update).matched_count:
        raise ClaimLost()


def _recover_stale_jobs(queue):
    now = utcnow()
    stale = {
        "status": "processing",
        "$or": [
            {"processing_started_at": {"$lte": now - STALE_AFTER}},
            {"processing_started_at": {"$exists": False}},
        ],
    }
    # SMTP acceptance followed by a process crash cannot be distinguished from
    # no delivery. Quarantine that window instead of blindly duplicating mail.
    queue.update_many(
        {"$and": [stale, {"$or": [
            {"sending_index": {"$exists": True}},
            {"delivery_tracking_version": {"$ne": 1}},
        ]}]},
        {
            "$set": {
                "status": "delivery_unknown", "updated_at": now,
                "error": "Delivery interrupted; operator reconciliation required",
            },
            "$unset": {"claim_token": ""},
        },
    )
    queue.update_many(
        {"$and": [stale, {"sending_index": {"$exists": False}},
                  {"delivery_tracking_version": 1}]},
        {
            "$set": {
                "status": "error", "next_attempt_at": now,
                "updated_at": now, "error": "Interrupted before delivery",
            },
            "$unset": {"claim_token": ""},
        },
    )
    # Old failures have no per-message receipt; a previous partial delivery is
    # unknowable. Keep them visible for reconciliation, not blind replay.
    queue.update_many(
        {"status": "error", "delivery_tracking_version": {"$ne": 1}},
        {"$set": {
            "status": "delivery_unknown", "updated_at": now,
            "error": "Legacy delivery requires operator reconciliation",
        }},
    )


def _eligible_messages(db, job):
    """Do not replay resolved moderation or disclose data to revoked admins."""
    messages = job.get("messages") or []
    if job.get("notification_type") not in {
        "initial_submission", "admin_pending_reminder", "city_assignment",
    }:
        return messages
    demo_id = job.get("demo_id")
    if isinstance(demo_id, str):
        try:
            demo_id = ObjectId(demo_id)
        except InvalidId:
            return None
    demo = db.demonstrations.find_one({"_id": demo_id})
    if not demo or any(demo.get(key) for key in ("approved", "rejected", "cancelled", "in_past")):
        return None
    if job.get("notification_type") == "city_assignment":
        if not has_live_assignment(demo):
            return None
        assignment = demo["city_assignment"]
        assigned = set(assignment.get("city_admin_ids") or [])
        allowed = {
            admin["email"] for admin in active_city_admins_for_city(db, assignment["city_key"])
            if admin["user_id"] in assigned
        }
        messages = [
            dict(message, recipients=[
                email for email in message.get("recipients", []) if email in allowed
            ])
            for message in messages
        ]
        if not any(message["recipients"] for message in messages):
            return None
    elif has_live_assignment(demo):
        return None
    return messages


def _send_messages(messages: List[Dict[str, Any]], queue, job, owner) -> int:
    delivered = set(job.get("delivered_indices") or [])
    for index, message in enumerate(messages or []):
        if index in delivered:
            continue
        template = message.get("template_name")
        recipients = [addr for addr in (message.get("recipients") or []) if addr]
        subject = message.get("subject")
        context = message.get("context") or {}

        if not template or not recipients or not subject:
            continue

        rendered_body = email_sender._env.get_template(template).render(context)
        email_job = EmailJob(
            subject=subject,
            recipients=recipients,
            body=rendered_body,
            html=rendered_body,
            instance_id=email_sender._instance_id,
        )
        _owned_update(queue, owner, {"$set": {
            "sending_index": index,
            "processing_started_at": utcnow(),
            "updated_at": utcnow(),
        }})
        try:
            if email_sender.send_email(email_job, raise_on_error=True) is not True:
                raise RuntimeError("Delivery not acknowledged")
        except (
            smtplib.SMTPConnectError, smtplib.SMTPAuthenticationError,
            smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused,
            smtplib.SMTPDataError, ConnectionRefusedError,
        ):
            # These rejections happen before SMTP accepts the message. Other
            # transport failures may occur *after* acceptance and are ambiguous.
            _owned_update(queue, owner, {"$unset": {"sending_index": ""}})
            raise
        _owned_update(queue, owner, {
            "$addToSet": {"delivered_indices": index},
            "$unset": {"sending_index": ""},
            "$set": {"updated_at": utcnow(), "messages_sent": len(delivered) + 1},
        })
        delivered.add(index)
    return len(delivered)


def _pending_admin_job_exists(queue, demo_id: ObjectId, cutoff: datetime) -> bool:
    return bool(
        queue.find_one(
            {
                "demo_id": {"$in": [demo_id, str(demo_id)]},
                "marks_admin_contact": True,
                "$or": [
                    {"status": {"$in": ["pending", "processing", "delivery_unknown"]}},
                    {"status": "error", "$or": [
                        {"attempts": {"$lt": MAX_ATTEMPTS}},
                        {"attempts": {"$exists": False}},
                        {"updated_at": {"$gte": cutoff}},
                    ]},
                    {
                        "status": "completed",
                        "$or": [
                            {"processed_at": {"$gte": cutoff}},
                            {"updated_at": {"$gte": cutoff}},
                            {"created_at": {"$gte": cutoff}},
                        ],
                    },
                ],
            }
        )
    )


def _enqueue_admin_reminders(db, max_to_enqueue: int = 50):
    """Ensure pending demos trigger at-least-daily reminders."""
    queue = db["demo_notifications_queue"]
    now = utcnow()
    cutoff = now - timedelta(hours=24)

    today = utcnow().date()

    query = {
        "$and": [
            {"approved": False},
            {"in_past": {"$ne": True}},
            {"cancelled": {"$ne": True}},
            {"$or": [{"rejected": {"$exists": False}}, {"rejected": False}]},
            NOT_ESCALATED_ASSIGNMENT_CLAUSE,
            {
                "$or": [
                    {"admin_notification_last_sent_at": {"$exists": False}},
                    {"admin_notification_last_sent_at": {"$lte": cutoff}},
                ]
            },
            {
                "$or": [
                    {"date": {"$gte": today.strftime("%Y-%m-%d")}},
                    {"date": {"$exists": False}},
                ]
            },
        ]
    }

    candidates = (
        db.demonstrations.find(query).sort("created_datetime", ASCENDING).limit(max_to_enqueue)
    )

    created = 0
    for demo in candidates:
        demo_id = demo["_id"]
        if _pending_admin_job_exists(queue, demo_id, cutoff):
            continue

        if demo.get("rejected"):
            continue

        try:
            demo_date = demo.get("date")
            if demo_date:
                parsed_date = datetime.strptime(demo_date, "%Y-%m-%d").date()
                if parsed_date < today:
                    continue
        except Exception:
            # If date parsing fails, prefer to skip reminder
            continue

        submitter = db.submitters.find_one({"demonstration_id": demo_id}) or {}

        try:
            approve_link = generate_demo_approve_link(str(demo_id))
            preview_link = generate_demo_preview_link(str(demo_id))
            reject_link = generate_demo_reject_link(str(demo_id))
        except Exception:
            logger.exception("Failed to generate admin action links for demo %s", demo_id)
            continue

        message = {
            "template_name": "admin_demo_approve_notification.html",
            "subject": f"Muistutus: {demo.get('title', 'mielenosoitus')} odottaa hyväksyntää",
            "recipients": ADMIN_RECIPIENTS,
            "context": {
                "title": demo.get("title"),
                "date": demo.get("date"),
                "city": demo.get("city"),
                "address": demo.get("address"),
                "submitter_name": submitter.get("submitter_name"),
                "submitter_email": submitter.get("submitter_email"),
                "submitter_role": submitter.get("submitter_role"),
                "approve_link": approve_link,
                "preview_link": preview_link,
                "reject_link": reject_link,
            },
        }

        try:
            queue.insert_one(
                {
                    "demo_id": demo_id,
                    "status": "pending",
                    "created_at": utcnow(),
                    "notification_type": "admin_pending_reminder",
                    "marks_admin_contact": True,
                    "messages": [message],
                }
            )
            created += 1
        except Exception:
            logger.exception("Failed to enqueue admin reminder for demo %s", demo_id)

    if created:
        logger.info("Enqueued %s admin reminder notifications for pending demos.", created)


def _mark_admin_contact(db, demo_id):
    if not demo_id:
        return
    if isinstance(demo_id, str):
        try:
            demo_id = ObjectId(demo_id)
        except Exception:
            return
    db.demonstrations.update_one(
        {"_id": demo_id},
        {"$set": {"admin_notification_last_sent_at": utcnow()}},
    )


def run(max_jobs: int = 25):
    """Process queued notification jobs for newly submitted demonstrations."""
    db = DatabaseManager().get_instance().get_db()
    queue = db["demo_notifications_queue"]
    processed = 0
    _recover_stale_jobs(queue)

    try:
        merge_duplicate_submissions(db=db, max_groups=25)
    except Exception:
        logger.exception("Failed to merge duplicate submission demos")

    # Ensure every pending demo gets at most one reminder per 24h
    _enqueue_admin_reminders(db)

    while processed < max_jobs:
        job = queue.find_one_and_update(
            {"$and": [
                {"status": {"$in": ["pending", "error", None]}},
                {"$or": [
                    {"attempts": {"$exists": False}},
                    {"attempts": {"$lt": MAX_ATTEMPTS}},
                ]},
                {"$or": [
                    {"next_attempt_at": {"$exists": False}},
                    {"next_attempt_at": {"$lte": utcnow()}},
                ]},
            ]},
            {
                "$set": {
                    "status": "processing",
                    "processing_started_at": utcnow(),
                    "updated_at": utcnow(),
                    "claim_token": uuid4().hex,
                    "delivery_tracking_version": 1,
                },
                "$inc": {"attempts": 1},
            },
            sort=[("created_at", ASCENDING), ("_id", ASCENDING)],
            return_document=ReturnDocument.AFTER,
        )
        if not job:
            break

        job_id = job["_id"]
        owner = {"_id": job_id, "status": "processing", "claim_token": job["claim_token"]}
        try:
            messages = _eligible_messages(db, job)
            if messages is None:
                _owned_update(queue, owner, {"$set": {
                    "status": "cancelled", "updated_at": utcnow(),
                    "cancellation_reason": "Moderation notification no longer applicable",
                }, "$unset": {"claim_token": ""}})
                processed += 1
                continue
            sent_count = _send_messages(messages, queue, job, owner)
            if job.get("marks_admin_contact"):
                _mark_admin_contact(db, job.get("demo_id"))
            _owned_update(
                queue,
                owner,
                {
                    "$set": {
                        "status": "completed",
                        "processed_at": utcnow(),
                        "messages_sent": sent_count,
                        "updated_at": utcnow(),
                    },
                    "$unset": {"claim_token": "", "error": "", "next_attempt_at": ""},
                },
            )
        except ClaimLost:
            logger.warning("Lost claim for demo notification job %s", job_id)
        except Exception as exc:
            # Do not persist/log exception text containing submitter data or links.
            current = queue.find_one(owner)
            if not current:
                processed += 1
                continue
            uncertain = "sending_index" in current
            logger.warning(
                "Demo notification job %s: %s on attempt %s/%s (%s)",
                job_id, "delivery_unknown" if uncertain else "error",
                job["attempts"], MAX_ATTEMPTS, type(exc).__name__,
            )
            queue.update_one(
                owner,
                {
                    "$set": {
                        "status": "delivery_unknown" if uncertain else "error",
                        "error": type(exc).__name__,
                        "next_attempt_at": utcnow() + timedelta(
                            seconds=60 * 2 ** (job["attempts"] - 1)
                        ),
                        "updated_at": utcnow(),
                    },
                    "$unset": {"claim_token": ""},
                },
            )
        processed += 1
