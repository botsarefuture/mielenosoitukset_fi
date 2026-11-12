"""Bounded canonical reconciliation for the outbound urgent-review channel."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
import os
from uuid import uuid4

from flask import current_app
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.urgent_review_alerts import HELSINKI, build_urgent_review_alert
from mielenosoitukset_fi.utils.urgent_review_telegram import DeliveryFailure, TelegramReviewTransport

LEASE = timedelta(minutes=10)
MAX_ATTEMPTS = 5
DISCOVERY_BATCH = 100
DELIVERY_BATCH = 10
CONTENT_FIELDS = {key: 1 for key in (
    "title", "city", "date", "start_time", "in_past", "approved", "rejected",
    "cancelled", "cancelled_at", "moderation_decision", "city_assignment",
)}


def _stored(now):
    return now.astimezone(UTC).replace(tzinfo=None)


def discover(db, chat_id, now):
    """Cycle a bounded date-scoped keyset; no full archive scan or RAM list."""
    day = now.astimezone(HELSINKI).date()
    # Spring's lost hour can put an under48h instant on the third following
    # calendar date. The shared instant policy still decides actual eligibility.
    dates = [day + timedelta(days=i) for i in range(4)]
    day_values = [value.isoformat() for value in dates]
    cursor = db.urgent_review_cursors.find_one({"_id": chat_id}) or {}
    query = {
        "approved": {"$ne": True}, "rejected": {"$ne": True}, "cancelled": {"$ne": True},
        "$or": [
            {"date": {"$in": day_values}},
            {"date": {"$gte": datetime.combine(day, datetime.min.time()),
                      "$lt": datetime.combine(day + timedelta(days=4), datetime.min.time())}},
        ],
    }
    if cursor.get("day") == day.isoformat() and cursor.get("after"):
        query["_id"] = {"$gt": cursor["after"]}
    last = None
    count = 0
    for demo in db.demonstrations.find(query, CONTENT_FIELDS).sort("_id", 1).limit(DISCOVERY_BATCH).max_time_ms(5000):
        count += 1
        last = demo["_id"]
        snapshot = build_urgent_review_alert(demo, now)
        if snapshot is None:
            continue
        key = f"{chat_id}:{demo['_id']}"
        try:
            db.urgent_review_outbox.update_one({"_id": key}, {"$setOnInsert": {
                "demo_id": demo["_id"], "chat_id": chat_id, "status": "ready",
                "created_at": _stored(now), "next_attempt_at": _stored(now), "attempts": 0,
            }}, upsert=True)
        except DuplicateKeyError:
            pass  # Another discoverer inserted this same demo/channel identity.
        db.urgent_review_outbox.update_one({
            "_id": key, "status": {"$in": ["watching", "settled", "done"]},
            "sent_hash": {"$ne": snapshot["text_sha256"]},
        }, {"$set": {
            "status": "ready", "next_attempt_at": _stored(now),
        }})
    db.urgent_review_cursors.update_one({"_id": chat_id}, {"$set": {
        "day": day.isoformat(), "after": last if count == DISCOVERY_BATCH else None,
    }}, upsert=True)


def _snapshot(db, job, now):
    demo = db.demonstrations.find_one({"_id": job["demo_id"]}, CONTENT_FIELDS)
    if demo:
        return build_urgent_review_alert(demo, now, has_message="message_id" in job)
    if "message_id" in job:
        text = "<b>Mielenosoitus poistettu</b>\nKäsittely päättynyt."
        return {"text": text, "text_sha256": sha256(text.encode()).hexdigest(), "state": "deleted"}
    return None


def _refresh_settled(db, chat_id, now):
    """Observe active receipts separately: unchanged history cannot consume sends."""
    queue = db.urgent_review_outbox
    stamp = _stored(now)
    queue.update_many({"chat_id": chat_id, "status": "settled", "observe_until": {"$lt": stamp}},
                      {"$set": {"status": "done"}})
    for job in queue.find({
        "chat_id": chat_id, "status": "settled", "next_attempt_at": {"$lte": stamp},
        "observe_until": {"$gte": stamp},
    }).sort([("next_attempt_at", 1), ("_id", 1)]).limit(DISCOVERY_BATCH):
        snapshot = _snapshot(db, job, now)
        changed = snapshot and snapshot["text_sha256"] != job.get("sent_hash")
        queue.update_one({"_id": job["_id"], "status": "settled", "sent_hash": job.get("sent_hash")}, {"$set": {
            "status": "ready" if changed else "settled",
            "next_attempt_at": stamp if changed else stamp + timedelta(minutes=2),
        }})


def reconcile(db, transport, now):
    """Claim records atomically; always derive delivery from current demo state."""
    queue = db.urgent_review_outbox
    stamp = _stored(now)
    stale = {"chat_id": transport.chat_id, "status": "processing", "claimed_at": {"$lte": stamp - LEASE}}
    # A first-send receipt lost at a crash is unknowable. Quarantine, never resend.
    queue.update_many({**stale, "phase": "sending", "message_id": {"$exists": False}}, {"$set": {
        "status": "delivery_unknown", "error": "First-send receipt requires reconciliation",
    }, "$unset": {"claim": ""}})
    queue.update_many(stale, {"$set": {
        "status": "retry", "next_attempt_at": stamp, "needs_reconcile": True,
    }, "$unset": {"claim": ""}})
    _refresh_settled(db, transport.chat_id, now)
    for _ in range(DELIVERY_BATCH):
        claim = uuid4().hex
        job = queue.find_one_and_update({
            "chat_id": transport.chat_id, "status": {"$in": ["ready", "retry"]},
            "next_attempt_at": {"$lte": stamp},
        }, {"$set": {"status": "processing", "phase": "claimed", "claim": claim, "claimed_at": stamp}},
            sort=[("next_attempt_at", 1), ("_id", 1)], return_document=ReturnDocument.AFTER)
        if not job:
            break
        owner = {"_id": job["_id"], "claim": claim, "status": "processing"}
        snapshot = _snapshot(db, job, now)
        if snapshot is None:
            # No fresh posts for events resolved/rescheduled between discovery and claim.
            queue.update_one(owner, {"$set": {"status": "watching"}, "$unset": {"claim": ""}})
            continue
        if snapshot["text_sha256"] == job.get("sent_hash") and not job.get("needs_reconcile"):
            queue.update_one(owner, {"$set": {
                "status": "settled", "attempts": 0, "next_attempt_at": stamp + timedelta(minutes=2),
            }, "$unset": {"claim": "", "error": ""}})
            continue
        if not queue.update_one(owner, {"$set": {"phase": "sending", "claimed_at": stamp}}).matched_count:
            continue
        try:
            message_id = transport.deliver(snapshot["text"], job.get("message_id"))
        except DeliveryFailure as exc:
            attempts = job.get("attempts", 0) + 1
            status = "delivery_unknown" if exc.uncertain else (
                "retry" if exc.retry_after is not None and attempts < MAX_ATTEMPTS else "blocked"
            )
            queue.update_one(owner, {"$set": {
                "status": status, "error": exc.code, "attempts": attempts,
                "needs_reconcile": "message_id" in job,
                "next_attempt_at": stamp + timedelta(seconds=max(exc.retry_after or 0, min(60 * 2 ** attempts, 3600))),
            }, "$unset": {"claim": ""}})
            continue
        # If this acknowledgement write fails, stale recovery retains an unknown
        # first send rather than guessing a new message ID and duplicating it.
        start = snapshot.get("starts_at")
        observe_until = _stored(start) + timedelta(days=1) if start else stamp + timedelta(days=2)
        queue.update_one(owner, {"$set": {
            "status": "done" if snapshot["state"] == "deleted" else "settled",
            "message_id": message_id, "sent_hash": snapshot["text_sha256"],
            "state": snapshot["state"], "attempts": 0, "updated_at": stamp,
            "observe_until": observe_until,
            "next_attempt_at": stamp + timedelta(minutes=2),
        }, "$unset": {"claim": "", "error": "", "needs_reconcile": ""}})


def run():
    """Opt-in job. Credentials stay in service environment, not documents/logs."""
    if current_app.config.get("URGENT_REVIEW_TELEGRAM_ENABLED") is not True:
        return
    transport = TelegramReviewTransport(
        os.environ.get("URGENT_REVIEW_TELEGRAM_TOKEN"),
        os.environ.get("URGENT_REVIEW_TELEGRAM_CHAT_ID"),
    )
    db = DatabaseManager.get_instance().get_db()
    db.urgent_review_outbox.create_index([("chat_id", 1), ("status", 1), ("next_attempt_at", 1)])
    now = datetime.now(UTC)
    discover(db, transport.chat_id, now)
    reconcile(db, transport, now)
    if db.urgent_review_outbox.count_documents({
        "chat_id": transport.chat_id, "status": {"$in": ["blocked", "delivery_unknown"]},
    }, limit=1):
        # Surface unresolved failures in the existing background-job UI each run,
        # rather than claiming green delivery because the queue was quarantined.
        raise RuntimeError("Urgent Telegram outbox requires operator reconciliation")
