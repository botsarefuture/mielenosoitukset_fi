"""Helpers for handling demonstration cancellations.

This module centralises cancellation link generation, verification and
notification dispatch so that new demonstrations can reliably provide
organisers with a secure cancellation flow.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional

from bson import ObjectId
from flask import url_for

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.emailer.EmailSender import EmailSender
from mielenosoitukset_fi.utils.logger import logger
from mielenosoitukset_fi.utils.notifications import create_notification
from mielenosoitukset_fi.utils.classes import Case

mongo = DatabaseManager().get_instance().get_db()
email_sender = EmailSender()

TOKEN_COLLECTION = "demo_cancellation_tokens"
TOKEN_EXPIRY_DAYS = 90


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _object_id(value) -> ObjectId:
    return value if isinstance(value, ObjectId) else ObjectId(value)


def _get_org(organization_id) -> Optional[dict]:
    if not organization_id:
        return None
    try:
        return mongo.organizations.find_one({"_id": _object_id(organization_id)})
    except Exception:
        return None


def _is_verified_official_contact(organizer: dict) -> bool:
    """Return True when organiser represents a verified organisation contact."""

    org = _get_org(organizer.get("organization_id"))
    if not org:
        return False

    if not org.get("verified"):
        return False

    org_email = (org.get("email") or "").lower()
    organizer_email = (organizer.get("email") or "").lower()
    return bool(org_email and organizer_email and org_email == organizer_email)


def queue_cancellation_links_for_demo(demo_doc: dict) -> None:
    """Send cancellation links to all organiser emails for a demonstration."""

    if not demo_doc:
        return

    demo_id = _object_id(demo_doc.get("_id"))
    seen_emails = set()

    for organizer in demo_doc.get("organizers", []):
        email = (organizer.get("email") or "").strip()
        if not email:
            continue

        email_key = email.lower()
        if email_key in seen_emails:
            continue

        official_contact = _is_verified_official_contact(organizer)

        token = secrets.token_urlsafe(32)
        token_doc = {
            "token_hash": _hash_token(token),
            "demo_id": demo_id,
            "organizer_email": email_key,
            "organizer_name": organizer.get("name"),
            "organization_id": organizer.get("organization_id"),
            "official_contact": official_contact,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(days=TOKEN_EXPIRY_DAYS),
            "used_at": None,
        }

        mongo[TOKEN_COLLECTION].update_one(
            {"demo_id": demo_id, "organizer_email": email_key},
            {"$set": token_doc},
            upsert=True,
        )

        try:
            cancellation_link = url_for("cancel_demo_with_token", token=token, _external=True)
        except Exception:
            logger.exception("Failed to build cancellation link for demo %s", demo_id)
            continue

        try:
            email_sender.queue_email(
                template_name="demo_cancellation_link.html",
                subject="Mielenosoituksen peruminen",
                recipients=[email],
                context={
                    "title": demo_doc.get("title", ""),
                    "date": demo_doc.get("date", ""),
                    "city": demo_doc.get("city", ""),
                    "cancellation_link": cancellation_link,
                    "official_contact": official_contact,
                },
            )
        except Exception:
            logger.exception("Failed to queue cancellation email to %s", email)

        seen_emails.add(email_key)


def fetch_cancellation_token(token: str) -> Optional[dict]:
    if not token:
        return None

    hashed = _hash_token(token)
    return mongo[TOKEN_COLLECTION].find_one({"token_hash": hashed})


def mark_token_used(record_id: ObjectId, reason: Optional[str] = None) -> None:
    updates: Dict[str, object] = {"used_at": datetime.utcnow()}
    if reason:
        updates["used_reason"] = reason
    mongo[TOKEN_COLLECTION].update_one({"_id": record_id}, {"$set": updates})


def request_cancellation_case(
    demo_doc: dict,
    reason: Optional[str],
    requester_email: Optional[str],
    official_contact: bool,
    source: str,
):
    """Create (or reuse) a cancellation case for a demonstration."""

    demo_id = _object_id(demo_doc.get("_id"))
    update_doc = {
        "cancellation_requested": True,
        "cancellation_requested_at": datetime.utcnow(),
        "cancellation_request_source": source,
        "cancellation_requested_by": {
            "email": requester_email,
            "official_contact": official_contact,
        },
    }
    if reason:
        update_doc["cancellation_reason"] = reason

    mongo.demonstrations.update_one({"_id": demo_id}, {"$set": update_doc})

    case_id = demo_doc.get("cancellation_case_id")
    if case_id:
        case = Case.get(case_id)
    else:
        case = Case.create_new(
            case_type="demo_cancellation_request",
            demo_id=demo_id,
            submitter={"email": requester_email},
            meta={"source": source, "official_contact": official_contact, "reason": reason},
        )
        mongo.demonstrations.update_one({"_id": demo_id}, {"$set": {"cancellation_case_id": case._id}})

    if case:
        case._add_history_entry(
            {
                "timestamp": datetime.utcnow(),
                "action": "cancellation_requested",
                "mech_action": source,
                "metadata": {
                    "reason": reason,
                    "official_contact": official_contact,
                    "requester_email": requester_email,
                },
            }
        )

    return case


def trigger_cancellation_notifications(demo_doc: dict) -> None:
    """Send in-app and email notifications to affected users."""

    demo = mongo.demonstrations.find_one({"_id": _object_id(demo_doc.get("_id"))}) or demo_doc
    demo_id = _object_id(demo.get("_id"))
    recipients = set()

    try:
        detail_link = url_for("demonstration_detail", demo_id=str(demo_id), _external=True)
    except Exception:
        detail_link = f"/demonstration/{demo_id}"

    payload = {"demo_title": demo.get("title", ""), "demo_id": str(demo_id)}

    attending_docs = mongo.demo_attending.find({"demo_id": demo_id, "attending": True})
    for doc in attending_docs:
        user_id = doc.get("user_id")
        if not user_id:
            continue
        try:
            create_notification(user_id, "demo_cancelled", payload, detail_link)
            user = mongo.users.find_one({"_id": user_id})
            if user and user.get("email"):
                recipients.add(user["email"])
        except Exception:
            logger.exception("Failed to notify user %s about cancellation", user_id)

    reminders = mongo.demo_reminders.find({"demonstration_id": demo_id})
    for reminder in reminders:
        email = reminder.get("user_email")
        if email:
            recipients.add(email)

    if not recipients:
        return

    context = {
        "title": demo.get("title", ""),
        "date": demo.get("date", ""),
        "city": demo.get("city", ""),
        "detail_link": detail_link,
    }

    for email in recipients:
        try:
            email_sender.queue_email(
                template_name="demo_cancelled_notification.html",
                subject="Mielenosoitus on peruttu",
                recipients=[email],
                context=context,
            )
        except Exception:
            logger.exception("Failed to queue cancellation notice to %s", email)


def cancel_demo(
    demo_doc: dict,
    cancelled_by: Dict[str, object],
    reason: Optional[str] = None,
    create_case: bool = True,
):
    """Mark a demonstration as cancelled and notify interested parties."""

    demo_id = _object_id(demo_doc.get("_id"))
    current_demo = mongo.demonstrations.find_one({"_id": demo_id}) or demo_doc

    if current_demo.get("cancelled"):
        logger.info("Demo %s already cancelled; skipping", demo_id)
        return False

    update_doc = {
        "cancelled": True,
        "cancelled_at": datetime.utcnow(),
        "cancelled_by": cancelled_by,
        "cancellation_requested": False,
    }
    if reason:
        update_doc["cancellation_reason"] = reason

    mongo.demonstrations.update_one({"_id": demo_id}, {"$set": update_doc})

    case = None
    if create_case:
        case_id = current_demo.get("cancellation_case_id")
        case = Case.get(case_id) if case_id else None
        if not case:
            case = Case.create_new(
                case_type="demo_cancelled",
                demo_id=demo_id,
                meta={"reason": reason, "cancelled_by": cancelled_by},
            )
            mongo.demonstrations.update_one({"_id": demo_id}, {"$set": {"cancellation_case_id": case._id}})

        if case:
            case._add_history_entry(
                {
                    "timestamp": datetime.utcnow(),
                    "action": "cancelled",
                    "mech_action": cancelled_by.get("source", "manual"),
                    "metadata": {"reason": reason, "cancelled_by": cancelled_by},
                }
            )

    trigger_cancellation_notifications(current_demo)
    return True
