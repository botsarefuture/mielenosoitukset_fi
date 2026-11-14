"""Pride banner carrier signup (docs/pride-banner-volunteers.md).

A second list on the fundraising reminder system (docs/fundraising-reminder.md).
Go stores signups in ``pride_banner_volunteers`` and consumes the one-time links.
This module mints the confirmation and unsubscribe tokens (only SHA-256 hashes are
stored), queues the plain-text mails through ``email_queue``, purges the data and
exports confirmed volunteers for the maintainers. It shares the token minting, flag
parsing, link base and retention constants with the reminder module. Nothing here
sends mail unless ``PRIDE_BANNER_MAILS_ENABLED`` is set.
"""
import csv
import io
from datetime import datetime, timezone

from pymongo import ReturnDocument

from mielenosoitukset_fi.emailer.EmailJob import EmailJob
from mielenosoitukset_fi.utils.fundraising_reminder import (
    CONFIRM_TTL, MAX_UNSUBSCRIBE_HASHES, PENDING_MAX_AGE, _flag, _mint, base_url,
)
from mielenosoitukset_fi.utils.logger import logger

COLLECTION = "pride_banner_volunteers"
ENABLED_FLAG = "PRIDE_BANNER_MAILS_ENABLED"
# Every row is deleted from this day, unless it carries a later ``retain_until``
# (set only after a new explicit consent). Finland's Prides end in September; the
# end of October leaves room for the follow-up and is the maintainer-adjustable limit.
PURGE_AFTER = datetime(2027, 10, 31, tzinfo=timezone.utc)
PAGE = "/pride-nakyvaksi"


def mails_enabled(environ=None):
    return _flag(ENABLED_FLAG, environ)


def _links(token, environ=None):
    base = base_url(environ)
    return (f"{base}{PAGE}?kantaja=peru#t={token}",
            f"{base}/api/pride-banner/volunteer/unsubscribe?t={token}")


def confirmation_message(token, unsubscribe_token, environ=None):
    base = base_url(environ)
    page, _ = _links(unsubscribe_token, environ)
    subject = "Vahvista ilmoittautumisesi banderollin kantajaksi"
    # No name or other free text from the form goes into the mail: the address
    # may belong to someone else, and the text would then arrive under our name.
    body = (
        "Hei,\n\n"
        "tämä osoite annettiin Mielenosoitukset.fi:n Pride näkyväksi -sivulla, kun ilmoittauduttiin banderollin kantajaksi. "
        "Jos ilmoittautuminen oli sinun, vahvista se tästä linkistä:\n\n"
        f"{base}{PAGE}?kantaja=vahvista#t={token}\n\n"
        "Linkki on voimassa 7 päivää ja toimii vain kerran. Ilman vahvistusta emme käytä osoitettasi mihinkään "
        "ja poistamme sen.\n\n"
        "Tavoitteemme on, että jokaisessa Pridessa on Mielenosoitukset.fi-banderolli, ja siihen tarvitaan kantajia. "
        "Ilmoittautuminen ei sido sinua mihinkään, ja voit perua sen milloin tahansa. "
        "Vahvistuksen jälkeen otamme yhteyttä myöhemmin ja sovimme tiedot yhdessä kanssasi. "
        "Käytämme tietoja vain tähän ja poistamme ne Pride-kauden jälkeen, ellet anna uutta lupaa.\n\n"
        "Jos et ilmoittautunut itse, voit jättää viestin huomiotta tai poistaa osoitteen heti:\n"
        f"{page}\n\n"
        f"Tietosuoja: {base}/privacy\n\n"
        "Mielenosoitukset.fi\n"
    )
    return subject, body


def _queue_document(job_id, email, subject, body, unsubscribe_token, environ=None):
    _, one_click = _links(unsubscribe_token, environ)
    job = EmailJob(
        subject=subject, recipients=[email], body=body, html=None,
        extra_headers={
            "List-Unsubscribe": f"<{one_click}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    ).to_dict()
    job["_id"] = job_id
    job["kind"] = "pride_banner_volunteer"
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
                f"pride-banner-confirm:{row['_id']}:{row.get('confirmation_count', 1)}",
                row["email"], subject, body, unsubscribe_token, environ))
            queued += 1
        except Exception as error:
            # Name only the error type: a traceback could print the document, which holds the raw token.
            logger.error("Could not queue a Pride banner confirmation (%s)", type(error).__name__)
            rows.update_one({"_id": row["_id"]}, {
                "$set": {"confirmation_sent_at": None},
                "$inc": {"confirmation_count": -1},
                "$unset": {"confirm_hash": "", "confirm_expires_at": ""},
                "$pull": {"unsubscribe_hashes": unsubscribe_hash}})
            break
    return {"enabled": True, "queued": queued}


def _after_retention(now):
    return {"$or": [{"retain_until": {"$exists": False}}, {"retain_until": None}, {"retain_until": {"$lte": now}}]}


def purge(db, now=None, dry_run=False):
    """Delete expired data; safe to run daily and without any flag.

    - Unconfirmed signups older than 14 days.
    - Everything after PURGE_AFTER, except rows with a later ``retain_until``.
    """
    now = now or datetime.now(timezone.utc)
    rows = db[COLLECTION]
    pending_filter = {"status": "pending", "created_at": {"$lt": now - PENDING_MAX_AGE}}
    result = {"dry_run": dry_run, "pending_expired": 0, "retention_ended": 0}
    if dry_run:
        result["pending_expired"] = rows.count_documents(pending_filter)
        if now >= PURGE_AFTER:
            result["retention_ended"] = rows.count_documents(_after_retention(now))
        return result
    result["pending_expired"] = rows.delete_many(pending_filter).deleted_count
    if now >= PURGE_AFTER:
        result["retention_ended"] = rows.delete_many(_after_retention(now)).deleted_count
    return result


def _cell(value):
    """Keep a spreadsheet from running text as a formula."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def export_confirmed(db):
    """CSV text of confirmed volunteers only, oldest first. Read-only."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["name", "email", "city", "pride", "unsure", "note", "confirmed_at"])
    for row in db[COLLECTION].find({"status": "confirmed"}).sort("confirmed_at", 1):
        writer.writerow([_cell(row.get("name")), _cell(row.get("email")), _cell(row.get("city")),
                         _cell(row.get("pride")), "yes" if row.get("unsure") else "", _cell(row.get("note")),
                         row["confirmed_at"].isoformat() if row.get("confirmed_at") else ""])
    return out.getvalue()
