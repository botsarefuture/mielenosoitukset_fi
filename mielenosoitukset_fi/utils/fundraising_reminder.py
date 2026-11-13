"""Fundraising opening reminder (docs/fundraising-reminder.md).

Go stores signups in ``fundraising_reminders`` and consumes the one-time links.
This module is the other half: it mints the confirmation and unsubscribe
tokens (only SHA-256 hashes are stored), queues the plain-text mails through
``email_queue``, sends the single opening reminder exactly once, and purges the
data after the retention date. Nothing here sends mail unless the flags below
are set, and the bulk reminder additionally needs the maintainer's approval flag.
"""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from mielenosoitukset_fi.emailer.EmailJob import EmailJob
from mielenosoitukset_fi.utils.logger import logger

COLLECTION = "fundraising_reminders"
SENT_COLLECTION = "fundraising_reminder_sent"

# 16.11.2026 00:00 Europe/Helsinki (UTC+2 in November).
SEND_AT = datetime(2026, 11, 15, 22, 0, tzinfo=timezone.utc)
# A reminder that is more than a day late is no longer the opening reminder.
SEND_UNTIL = SEND_AT + timedelta(days=1)
# The collection ends 15.2.2027; every row is purged 30 days later.
COLLECTION_END = datetime(2027, 2, 15, tzinfo=timezone.utc)
PURGE_AFTER = COLLECTION_END + timedelta(days=30)
CONFIRM_TTL = timedelta(days=7)
# Unconfirmed signups are erased once their link has expired and a grace week passed.
PENDING_MAX_AGE = CONFIRM_TTL + timedelta(days=7)
MAX_UNSUBSCRIBE_HASHES = 6

ENABLED_FLAG = "FUNDRAISING_REMINDER_MAILS_ENABLED"
APPROVED_FLAG = "FUNDRAISING_REMINDER_BULK_SEND_APPROVED"
BASE_URL_ENV = "FUNDRAISING_REMINDER_BASE_URL"
DEFAULT_BASE_URL = "https://mielenosoitukset.fi"


def _flag(name, environ=None):
    value = (environ if environ is not None else os.environ).get(name, "")
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def mails_enabled(environ=None):
    return _flag(ENABLED_FLAG, environ)


def bulk_send_approved(environ=None):
    return _flag(APPROVED_FLAG, environ)


def base_url(environ=None):
    return ((environ if environ is not None else os.environ).get(BASE_URL_ENV) or DEFAULT_BASE_URL).rstrip("/")


def _mint():
    token = secrets.token_urlsafe(32)
    return token, hashlib.sha256(token.encode()).hexdigest()


def _unsubscribe_links(token, environ=None):
    base = base_url(environ)
    return (f"{base}/ker%C3%A4ys?muistutus=peru#t={token}",
            f"{base}/api/fundraising/reminder/unsubscribe?t={token}")


def confirmation_message(token, unsubscribe_token, environ=None):
    base = base_url(environ)
    page, _ = _unsubscribe_links(unsubscribe_token, environ)
    subject = "Vahvista muistutuksen tilaus: Mielenosoitukset.fi:n pienkeräys"
    body = (
        "Hei,\n\n"
        "tämä osoite annettiin Mielenosoitukset.fi:n sivulla, kun pyydettiin muistutusta pienkeräyksen alkamisesta. "
        "Jos pyyntö oli sinun, vahvista tilaus tästä linkistä:\n\n"
        f"{base}/ker%C3%A4ys?muistutus=vahvista#t={token}\n\n"
        "Linkki on voimassa 7 päivää ja toimii vain kerran. Ilman vahvistusta emme lähetä sinulle mitään "
        "ja poistamme osoitteen.\n\n"
        "Vahvistuksen jälkeen lähetämme sinulle yhden viestin, kun keräys alkaa 16.11.2026. "
        "Osoitetta ei käytetä mihinkään muuhun.\n\n"
        "Jos et pyytänyt tätä, voit jättää viestin huomiotta tai poistaa osoitteen heti:\n"
        f"{page}\n\n"
        f"Tietosuoja: {base}/privacy\n\n"
        "Mielenosoitukset.fi\n"
    )
    return subject, body


def reminder_message(unsubscribe_token, environ=None):
    base = base_url(environ)
    page, _ = _unsubscribe_links(unsubscribe_token, environ)
    subject = "Mielenosoitukset.fi:n pienkeräys on nyt auki"
    body = (
        "Hei,\n\n"
        "Mielenosoitukset.fi:n pienkeräys alkoi 16.11.2026. Lahjoitusohjeet ja keräyksen tiedot ovat sivulla:\n\n"
        f"{base}/ker%C3%A4ys\n\n"
        "Lahjoita vain keräysaikana. Keräysaika ja pienkeräysnumero näkyvät sivulla.\n\n"
        "Tämä on ainoa viesti, jonka lähetämme tilauksesi perusteella. Voit poistaa osoitteesi heti:\n"
        f"{page}\n\n"
        f"Tietosuoja: {base}/privacy\n\n"
        "Mielenosoitukset.fi\n"
    )
    return subject, body


def _queue_document(job_id, email, subject, body, unsubscribe_token, environ=None):
    _, one_click = _unsubscribe_links(unsubscribe_token, environ)
    job = EmailJob(
        subject=subject, recipients=[email], body=body, html=None,
        extra_headers={
            "List-Unsubscribe": f"<{one_click}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    ).to_dict()
    job["_id"] = job_id
    job["kind"] = "fundraising_reminder"
    return job


def send_confirmations(db, now=None, limit=100, environ=None):
    """Queue a confirmation mail for each pending signup that asked for one.

    The claim (``confirmation_sent_at``) is set atomically before the mail is
    queued, so two overlapping runs never queue two mails for one request.
    """
    if not mails_enabled(environ):
        return {"enabled": False, "queued": 0}
    now = now or datetime.now(timezone.utc)
    rows = db[COLLECTION]
    queued = 0
    for _ in range(limit):
        confirm_token, confirm_hash = _mint()
        unsubscribe_token, unsubscribe_hash = _mint()
        row = rows.find_one_and_update(
            {"status": "pending", "confirmation_requested_at": {"$ne": None}, "confirmation_sent_at": None},
            {"$set": {"confirmation_sent_at": now, "confirm_hash": confirm_hash,
                      "confirm_expires_at": now + CONFIRM_TTL},
             "$inc": {"confirmation_count": 1},
             "$push": {"unsubscribe_hashes": {"$each": [unsubscribe_hash], "$slice": -MAX_UNSUBSCRIBE_HASHES}}},
            sort=[("confirmation_requested_at", 1)], return_document=ReturnDocument.AFTER,
        )
        if row is None:
            break
        subject, body = confirmation_message(confirm_token, unsubscribe_token, environ)
        try:
            db.email_queue.insert_one(_queue_document(
                f"fundraising-confirm:{row['_id']}:{row.get('confirmation_count', 1)}",
                row["email"], subject, body, unsubscribe_token, environ))
            queued += 1
        except Exception:
            logger.exception("Could not queue a fundraising reminder confirmation")
            rows.update_one({"_id": row["_id"]}, {
                "$set": {"confirmation_sent_at": None},
                "$inc": {"confirmation_count": -1},
                "$unset": {"confirm_hash": "", "confirm_expires_at": ""},
                "$pull": {"unsubscribe_hashes": unsubscribe_hash}})
            break
    return {"enabled": True, "queued": queued}


def reminder_report(db, now=None):
    """Counts for the dry run; reads only."""
    rows = db[COLLECTION]
    now = now or datetime.now(timezone.utc)
    return {
        "window_open": SEND_AT <= now <= SEND_UNTIL,
        "would_send": rows.count_documents({"status": "confirmed", "reminder_claimed_at": None}),
        "confirmed_total": rows.count_documents({"status": "confirmed"}),
        "pending": rows.count_documents({"status": "pending"}),
        "already_claimed": rows.count_documents({"status": "confirmed", "reminder_claimed_at": {"$ne": None}}),
        "claimed_never_queued": rows.count_documents(
            {"reminder_claimed_at": {"$ne": None}, "reminder_queued_at": None}),
    }


def send_reminders(db, now=None, dry_run=False, limit=500, environ=None):
    """Queue the one opening reminder for every confirmed signup, once.

    A dry run lists counts and writes nothing. A real run needs the mail flag,
    the maintainer's bulk-send approval flag and the clock inside the send
    window (16.11.2026 00:00 Helsinki, for a day). Never twice, by three guards:
    the per-row claim, a marker keyed by the hash of the address (so even two
    rows for one address cannot both send), and a fixed queue id per row.
    """
    now = now or datetime.now(timezone.utc)
    if dry_run:
        return {"dry_run": True, **reminder_report(db, now)}
    if not mails_enabled(environ) or not bulk_send_approved(environ):
        return {"sent": 0, "reason": "not enabled or not approved"}
    if not (SEND_AT <= now <= SEND_UNTIL):
        return {"sent": 0, "reason": "outside the send window"}
    rows = db[COLLECTION]
    sent_markers = db[SENT_COLLECTION]
    queued = skipped = 0
    for _ in range(limit):
        unsubscribe_token, unsubscribe_hash = _mint()
        row = rows.find_one_and_update(
            {"status": "confirmed", "reminder_claimed_at": None},
            {"$set": {"reminder_claimed_at": now},
             "$push": {"unsubscribe_hashes": {"$each": [unsubscribe_hash], "$slice": -MAX_UNSUBSCRIBE_HASHES}}},
            return_document=ReturnDocument.AFTER,
        )
        if row is None:
            break
        marker_id = hashlib.sha256(row["email"].encode()).hexdigest()
        try:
            sent_markers.insert_one({"_id": marker_id, "created_at": now})
        except DuplicateKeyError:
            skipped += 1
            continue
        subject, body = reminder_message(unsubscribe_token, environ)
        try:
            db.email_queue.insert_one(_queue_document(
                f"fundraising-reminder:{row['_id']}", row["email"], subject, body, unsubscribe_token, environ))
        except DuplicateKeyError:
            skipped += 1
            continue
        except Exception:
            logger.exception("Could not queue the fundraising reminder")
            sent_markers.delete_one({"_id": marker_id})
            rows.update_one({"_id": row["_id"]}, {"$set": {"reminder_claimed_at": None},
                                                   "$pull": {"unsubscribe_hashes": unsubscribe_hash}})
            break
        rows.update_one({"_id": row["_id"]}, {"$set": {"reminder_queued_at": now}})
        queued += 1
    return {"sent": queued, "skipped": skipped}


def purge(db, now=None, dry_run=False):
    """Delete expired data; safe to run daily and without any flag.

    - Unconfirmed signups older than 14 days.
    - Everything, including the send markers, after PURGE_AFTER
      (30 days after the collection ends), except rows with a later
      ``retain_until`` (reserved for a later explicit consent).
    """
    now = now or datetime.now(timezone.utc)
    rows = db[COLLECTION]
    pending_filter = {"status": "pending", "created_at": {"$lt": now - PENDING_MAX_AGE}}
    result = {"dry_run": dry_run, "pending_expired": 0, "retention_ended": 0, "markers": 0}
    if dry_run:
        result["pending_expired"] = rows.count_documents(pending_filter)
        if now >= PURGE_AFTER:
            result["retention_ended"] = rows.count_documents(_after_retention(now))
            result["markers"] = db[SENT_COLLECTION].count_documents({})
        return result
    result["pending_expired"] = rows.delete_many(pending_filter).deleted_count
    if now >= PURGE_AFTER:
        result["retention_ended"] = rows.delete_many(_after_retention(now)).deleted_count
        if rows.count_documents({}) == 0:
            result["markers"] = db[SENT_COLLECTION].delete_many({}).deleted_count
    return result


def _after_retention(now):
    return {"$or": [{"retain_until": {"$exists": False}}, {"retain_until": None}, {"retain_until": {"$lte": now}}]}
