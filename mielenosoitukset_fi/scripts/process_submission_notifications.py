from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

from bson import ObjectId
from pymongo import ASCENDING, ReturnDocument

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.emailer.EmailSender import EmailSender
from mielenosoitukset_fi.utils.logger import logger
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


def _send_messages(messages: List[Dict[str, Any]]) -> int:
    sent = 0
    for message in messages or []:
        template = message.get("template_name")
        recipients = [addr for addr in (message.get("recipients") or []) if addr]
        subject = message.get("subject")
        context = message.get("context") or {}

        if not template or not recipients or not subject:
            continue

        email_sender.queue_email(
            template_name=template,
            subject=subject,
            recipients=recipients,
            context=context,
        )
        sent += 1
    return sent


def _pending_admin_job_exists(queue, demo_id: ObjectId) -> bool:
    return bool(
        queue.find_one(
            {
                "demo_id": demo_id,
                "marks_admin_contact": True,
                "status": {"$in": ["pending", "processing"]},
            }
        )
    )


def _enqueue_admin_reminders(db, max_to_enqueue: int = 50):
    """Ensure pending demos trigger at-least-daily reminders."""
    queue = db["demo_notifications_queue"]
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=24)

    today = datetime.utcnow().date()

    query = {
        "$and": [
            {"approved": False},
            {"in_past": {"$ne": True}},
            {"cancelled": {"$ne": True}},
            {"$or": [{"rejected": {"$exists": False}}, {"rejected": False}]},
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
        if _pending_admin_job_exists(queue, demo_id):
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
                    "created_at": datetime.utcnow(),
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
        {"$set": {"admin_notification_last_sent_at": datetime.utcnow()}},
    )


def run(max_jobs: int = 25):
    """Process queued notification jobs for newly submitted demonstrations."""
    db = DatabaseManager().get_instance().get_db()
    queue = db["demo_notifications_queue"]
    processed = 0

    try:
        merge_duplicate_submissions(db=db, max_groups=25)
    except Exception:
        logger.exception("Failed to merge duplicate submission demos")

    # Ensure every pending demo gets at most one reminder per 24h
    _enqueue_admin_reminders(db)

    while processed < max_jobs:
        job = queue.find_one_and_update(
            {"status": {"$in": ["pending", None]}},
            {
                "$set": {
                    "status": "processing",
                    "processing_started_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            },
            sort=[("created_at", ASCENDING)],
            return_document=ReturnDocument.AFTER,
        )
        if not job:
            break

        job_id = job["_id"]
        try:
            sent_count = _send_messages(job.get("messages"))
            if job.get("marks_admin_contact"):
                _mark_admin_contact(db, job.get("demo_id"))
            queue.update_one(
                {"_id": job_id},
                {
                    "$set": {
                        "status": "completed",
                        "processed_at": datetime.utcnow(),
                        "messages_sent": sent_count,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
        except Exception as exc:
            logger.exception("Failed to process demo notification job %s", job_id)
            queue.update_one(
                {"_id": job_id},
                {
                    "$set": {
                        "status": "error",
                        "error": str(exc),
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
        processed += 1
