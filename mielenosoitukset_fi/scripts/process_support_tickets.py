"""Support ticket ingress — polls the tuki@ mailbox and turns emails into cases.

Design
------
- Runs as a background job (see background_jobs/definitions.py) which is
  leadership-coordinated across gunicorn workers, so exactly one poller runs.
- Connects to the configured IMAP server (default mail.luova.club) and processes
  unseen messages in the tuki mailbox.
- Creates a ``Case`` with ``case_type="support_ticket"`` for each new email,
  reusing the existing running-number sequence (ticket IDs like ``#100042``).
- Detects the *real* human sender from the HTML contact-form wrapper
  (``Viestin lähettäjä: Name <email>``) and replies to THAT address — never to
  the ``no-reply@mielenosoitukset.fi`` wrapper sender.
- Auto-replies with the ticket id + SLA note and instructs the user to write
  URGENT for urgent matters. Follow-up emails containing the urgent keyword
  are relayed to the escalation mailbox and mark the case
  ``meta.superior_needed``.
- Emails are flagged ``\\Seen`` after processing (deduplicated by
  ``meta.ticket.message_id`` in Mongo to stay idempotent across retries).
"""

from __future__ import annotations

import email
import imaplib
import re
import uuid
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any, Dict, List, Optional, Tuple

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.emailer.EmailJob import Sender
from mielenosoitukset_fi.emailer.EmailSender import EmailSender
from mielenosoitukset_fi.utils.classes import Case
from mielenosoitukset_fi.utils.logger import logger
from mielenosoitukset_fi.utils.time_utils import utcnow
from config import Config

# Regex for the contact-form HTML wrapper produced by
# templates/emails/customer_support/new_ticket.html:
#   <strong>Viestin lähettäjä:</strong> Name <email>
# Operates on html.unescape()d text so entity-encoded Finnish (l&auml;hett&auml;j&auml;)
# and angle brackets (&lt; &gt;) match reliably.
_SENDER_WRAPPER_RE = re.compile(
    r"Viestin[ _]l[äa]hett[äa]j[äa]:\s*</strong>\s*"
    r"(.*?)\s*<([^>]+)>",
    re.IGNORECASE,
)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# Plain-text alternative in case the HTML wrapper arrives differently.
_PLAIN_SENDER_LABEL_RE = re.compile(
    r"Viestin[ _]l[äa]hett[äa]j[äa]\s*:\s*([^<@\n]*?)\s*<([^>]+)>",
    re.IGNORECASE,
)

# Static fallback list blended with the admin-managed Mongo blocklist.
def _load_blocklist(mongo) -> List[str]:
    """Return all blocked sender patterns (config static list + Mongo list).

    Patterns are stored lowercased. Supported forms:
    - ``user@example.com``  → block that exact address
    - ``*@example.com``     → block example.com and every subdomain
    - ``example.com``       → same as ``*@example.com``
    """
    entries = list(getattr(Config, "TICKET_IGNORED_SENDERS", []) or [])
    for doc in mongo.support_ticket_blocklist.find({}, {"pattern": 1}):
        entries.append(doc.get("pattern", ""))
    return [e.strip().lower() for e in entries if e and e.strip()]


def _sender_matches_pattern(sender_email: str, pattern: str) -> bool:
    """Match a lowercased sender address against one blocklist pattern."""
    if "@" not in sender_email:
        return False
    # ``user@example.com`` → block that exact address.
    if "@" in pattern and not pattern.startswith("*@"):
        return sender_email == pattern
    # ``*@example.com`` and bare ``example.com`` → block example.com and
    # every subdomain (e.g. m.example.com, deep.sub.example.com).
    if pattern.startswith("*@"):
        domain = pattern[2:]
    else:
        domain = pattern
    if not domain:
        return False
    domain_part = sender_email.split("@", 1)[1]
    return domain_part == domain or domain_part.endswith("." + domain)


def _sender_is_blocked(sender_email: str, blocklist: List[str]) -> bool:
    """Check a sender against the blocklist (exact, ``*@domain``, or bare domain)."""
    if not sender_email:
        return False
    lower = sender_email.strip().lower()
    return any(_sender_matches_pattern(lower, p) for p in blocklist)


def _ticket_sender(config):
    """Build a Sender that sends from the tuki@ ticket mailbox via SMTP."""
    username = getattr(config, "TICKET_IMAP_USERNAME", "")
    return Sender(
        email_address=username,
        email_server=getattr(config, "TICKET_SMTP_SERVER", getattr(config, "TICKET_IMAP_SERVER", "")),
        email_port=int(getattr(config, "TICKET_SMTP_PORT", 587)),
        username=username,
        password=getattr(config, "TICKET_IMAP_PASSWORD", ""),
        use_tls=bool(getattr(config, "TICKET_SMTP_USE_TLS", True)),
    )


def _decode_header_value(value: Optional[str]) -> str:
    """Decode RFC 2047 encoded header values (e.g. '=?utf-8?Q?...?=')."""
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return str(value)


def _get_body(msg: Message) -> Tuple[str, str]:
    """Return (plain_text, html) for a parsed email message."""
    plain_parts: List[str] = []
    html_parts: List[str] = []

    def walk(part: Message) -> None:
        if part.is_multipart():
            for sub in part.get_payload():
                walk(sub)
            return
        ctype = (part.get_content_type() or "").lower()
        charset = part.get_content_charset() or "utf-8"
        payload = part.get_payload(decode=True)
        if not payload:
            return
        try:
            text = payload.decode(charset, errors="replace")
        except (LookupError, UnicodeDecodeError):
            text = payload.decode("utf-8", errors="replace")
        if ctype == "text/plain":
            plain_parts.append(text)
        elif ctype == "text/html":
            html_parts.append(text)

    walk(msg)
    return "\n".join(plain_parts), "\n".join(html_parts)


def _html_to_text(html: str) -> str:
    """Very small HTML→text converter good enough for ticket messages."""
    text = re.sub(r"<(br|/p|/div|/li|/tr)\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_sender_from_body(msg: Message, html: str, plain: str) -> Optional[Tuple[str, str]]:
    """Look for the contact-form wrapper and return (name, email) or None."""
    if html:
        # Unescape HTML entities first (&auml; → ä, &lt; → <, &gt; → >)
        # so the regex can match both entity-encoded and raw forms.
        decoded_html = unescape(html)
        m = _SENDER_WRAPPER_RE.search(decoded_html)
        if m:
            name = m.group(1).strip().strip("<>")
            email_addr = m.group(2).strip()
            return (name or email_addr, email_addr)
    if plain:
        m = _PLAIN_SENDER_LABEL_RE.search(plain)
        if m:
            name = m.group(1).strip()
            email_addr = m.group(2).strip()
            return (name or email_addr, email_addr)
    return None


def _extract_from_header(from_value: Optional[str]) -> Optional[Tuple[str, str]]:
    """Return (name, email) from the From header, or None."""
    if not from_value:
        return None
    decoded = _decode_header_value(from_value)
    m = _EMAIL_RE.search(decoded)
    if not m:
        return None
    email_addr = m.group(0)
    name = decoded.replace(email_addr, "").strip(" <>\"'")
    return (name or email_addr, email_addr)


def _message_text(msg: Message) -> str:
    """Human-readable body to store may look to long: pick the text version
    if present, otherwise the html stripped of tags."""
    plain, html = _get_body(msg)
    if plain.strip():
        return plain.strip()
    if html.strip():
        return _html_to_text(html)
    return ""


def _contains_urgent(texts: List[str], keyword: str) -> bool:
    if not keyword:
        return False
    return any(keyword.upper() in (t or "").upper() for t in texts)


def _parse_message(raw: bytes, keyword: str) -> Dict[str, Any]:
    """Parse a raw IMAP email into a normalised dict."""
    msg = email.message_from_bytes(raw)
    subject = _decode_header_value(msg.get("Subject"))
    from_value = msg.get("From")
    plain, html = _get_body(msg)

    wrapper_sender = _extract_sender_from_body(msg, html, plain)
    header_sender = _extract_from_header(from_value)

    # Prefer the human sender from the contact-form wrapper; fall back to the
    # From header. Never auto-reply to the no-reply wrapper account.
    if wrapper_sender:
        sender_name, sender_email = wrapper_sender
    elif header_sender:
        sender_name, sender_email = header_sender
    else:
        sender_name, sender_email = "", ""

    return {
        "message_id": (msg.get("Message-ID") or "").strip() or None,
        "in_reply_to": (msg.get("In-Reply-To") or "").strip() or None,
        "references": (msg.get("References") or "").strip() or None,
        "received_at": parsedate_to_datetime(msg.get("Date")) if msg.get("Date") else None,
        "subject": subject,
        "from_header": from_value or "",
        "sender_name": sender_name,
        "sender_email": sender_email,
        "body": _message_text(msg),
        "html_body": html,
        "urgent": _contains_urgent([subject, plain, html], keyword),
        "from_wrapper": bool(wrapper_sender),
    }


def _find_existing_by_reply(parsed: Dict[str, Any], mongo):
    """Find an existing support ticket that this email replies to.

    Matches on In-Reply-To / References against:
    - the original ticket's stored message_id (meta.ticket.message_id)
    - the ticket's outbound replies (meta.ticket.reply_message_ids)
    - follow-up messages already appended to the case (suggestion.messages)
    """
    candidates = [parsed.get("in_reply_to"), parsed.get("references"), parsed.get("message_id")]
    for value in candidates:
        if not value:
            continue
        # mail clients can send multiple, space-separated IDs
        for ref in re.findall(r"<[^>]+>", value):
            existing = mongo.cases.find_one(
                {
                    "type": "support_ticket",
                    "$or": [
                        {"meta.ticket.message_id": ref},
                        {"meta.ticket.reply_message_ids": ref},
                        {"suggestion.messages.message_id": ref},
                    ],
                }
            )
            if existing:
                return existing
    return None


def _process_email(raw: bytes, mongo, email_sender, config, blocklist: Optional[List[str]] = None) -> Optional[int]:
    """Process one raw email into a support ticket. Returns running_num or None."""
    keyword = getattr(config, "TICKET_URGENT_KEYWORD", "URGENT")
    parsed = _parse_message(raw, keyword)
    message_id = parsed["message_id"]

    # Deduplicate: if we already created a ticket for this message-id, skip.
    if message_id:
        existing = mongo.cases.find_one(
            {
                "type": "support_ticket",
                "$or": [
                    {"meta.ticket.message_id": message_id},
                    {"suggestion.messages.message_id": message_id},
                ],
            }
        )
        if existing:
            logger.info(
                "Skipping already-processed ticket email message_id=%s",
                message_id,
            )
            return None

    # Do not process purely-internal/auto responder emails.
    sender_email = parsed["sender_email"]
    if not sender_email:
        logger.warning(
            "Skipping email without extractable sender (subject=%r)",
            parsed["subject"][:80],
        )
        return None

    # Admin-maintained blocklist: skip senders added by admins (exact address
    # or whole domain incl. subdomains). The email is still flagged \\Seen by
    # the caller so it is not reprocessed.
    if blocklist is None:
        blocklist = _load_blocklist(mongo)
    if _sender_is_blocked(sender_email, blocklist):
        logger.info("Skipping blocked support-ticket sender %s", sender_email)
        return None

    internal_senders = {
        getattr(config, "TICKET_SENDER", ""),
        getattr(config, "MAIL_DEFAULT_SENDER", ""),
    }
    our_domain = getattr(config, "TICKET_IMAP_USERNAME", "").split("@")[-1]
    if sender_email.split("@")[-1].lower() == our_domain.lower():
        logger.info("Skipping internal-domain email from %s", sender_email)
        return None

    urgent = parsed["urgent"]

    # Follow-up on an existing ticket: append the message, relay URGENT,
    # do not create a second ticket.
    parent = _find_existing_by_reply(parsed, mongo)
    if parent:
        _append_followup(parent, parsed, mongo, email_sender, config)
        return parent.get("running_num")

    meta: Dict[str, Any] = {
        "ticket": {
            "source": "email",
            "message_id": message_id,
            "in_reply_to": parsed["in_reply_to"],
            "subject": parsed["subject"],
            "from_header": parsed["from_header"],
            "from_wrapper": parsed["from_wrapper"],
        },
        "urgent": urgent,
    }
    if urgent:
        meta["superior_needed"] = True
        meta["escalation_emailed_to"] = getattr(config, "TICKET_ESCALATION_EMAIL", "")

    case = Case.create_new(
        case_type="support_ticket",
        submitter={
            "submitter_name": parsed["sender_name"],
            "submitter_email": sender_email,
        },
        suggestion={
            "message": parsed["body"],
            "html_message": parsed["html_body"],
            "subject": parsed["subject"],
        },
        meta=meta,
    )

    # Auto-reply with the ticket id + SLA note. The reply goes to the real
    # human sender only. Its Message-ID is kept so the user's reply can be
    # threaded back onto this ticket.
    ticket_label = f"#{case.running_num}"
    auto_reply_msg_id = _queue_auto_reply(
        email_sender, config, sender_email, ticket_label, parsed["subject"], in_reply_to=message_id
    )

    urgent_msg_id = None
    if urgent:
        urgent_msg_id = _queue_urgent_alert(
            email_sender,
            config,
            sender_email,
            ticket_label,
            parsed["subject"],
            parsed["body"],
        )

    outbound_ids = [mid for mid in (auto_reply_msg_id, urgent_msg_id) if mid]
    if outbound_ids:
        mongo.cases.update_one(
            {"_id": case._id},
            {"$addToSet": {"meta.ticket.reply_message_ids": {"$each": outbound_ids}}},
        )

    logger.info(
        "Created support ticket %s from %s (urgent=%s)",
        ticket_label,
        sender_email,
        urgent,
    )
    return case.running_num


def _append_followup(parent, parsed: Dict[str, Any], mongo, email_sender, config) -> None:
    """Append a follow-up email to an existing support ticket."""
    ticket_label = f"#{parent.get('running_num')}"
    now = utcnow()
    followup = {
        "timestamp": now,
        "message_id": parsed.get("message_id"),
        "from_email": parsed["sender_email"],
        "from_name": parsed["sender_name"],
        "subject": parsed["subject"],
        "message": parsed["body"],
    }
    update: Dict[str, Any] = {
        "$push": {"suggestion.messages": followup},
        "$set": {"updated_at": now},
    }
    if parsed["urgent"]:
        update["$set"].update(
            {
                "meta.urgent": True,
                "meta.superior_needed": True,
                "meta.escalation_emailed_to": getattr(config, "TICKET_ESCALATION_EMAIL", ""),
            }
        )
        urgent_msg_id = _queue_urgent_alert(
            email_sender,
            config,
            parsed["sender_email"],
            ticket_label,
            parsed["subject"],
            parsed["body"],
        )
        if urgent_msg_id:
            update["$addToSet"] = {"meta.ticket.reply_message_ids": urgent_msg_id}
    mongo.cases.update_one({"_id": parent["_id"]}, update)
    logger.info(
        "Appended follow-up to ticket %s from %s (urgent=%s)",
        ticket_label,
        parsed["sender_email"],
        parsed["urgent"],
    )


def _new_outbound_message_id() -> str:
    """Generate a Message-ID for an outbound ticket email (threading anchor)."""
    return f"<{uuid.uuid4()}@mielenosoitukset.fi>"


def _queue_auto_reply(email_sender, config, reply_to: str, ticket_label: str, original_subject: str, in_reply_to: Optional[str] = None) -> str:
    sla_hours = getattr(config, "TICKET_SLA_HOURS", 48)
    keyword = getattr(config, "TICKET_URGENT_KEYWORD", "URGENT")
    message_id = _new_outbound_message_id()
    extra_headers = {"Message-ID": message_id}
    if in_reply_to:
        extra_headers["In-Reply-To"] = in_reply_to
        extra_headers["References"] = in_reply_to
    email_sender.queue_email(
        template_name="customer_support/ticket_auto_reply.html",
        subject=f"Vahvistus tukipyynnöstä {ticket_label}",
        recipients=[reply_to],
        sender=_ticket_sender(config),
        extra_headers=extra_headers,
        context={
            "ticket_id": ticket_label,
            "sla_hours": sla_hours,
            "urgent_keyword": keyword,
        },
    )
    return message_id


def _queue_urgent_alert(email_sender, config, sender_email: str, ticket_label: str, subject: str, body: str) -> Optional[str]:
    escalation_email = getattr(config, "TICKET_ESCALATION_EMAIL", "")
    if not escalation_email:
        logger.warning("No TICKET_ESCALATION_EMAIL configured; cannot relay URGENT.")
        return None
    message_id = _new_outbound_message_id()
    email_sender.queue_email(
        template_name="customer_support/ticket_urgent_alert.html",
        subject=f"URGENT tukipyyntö {ticket_label}: {subject[:80]}",
        recipients=[escalation_email],
        sender=_ticket_sender(config),
        extra_headers={"Message-ID": message_id},
        context={
            "ticket_id": ticket_label,
            "from_email": sender_email,
            "subject": subject,
            "message": body,
        },
    )
    logger.info("Queued URGENT alert for %s to %s", ticket_label, escalation_email)
    return message_id


def queue_admin_reply(email_sender, config, case, reply_to: str, message: str, admin_label: str = "") -> str:
    """Queue an admin reply to a support ticket and record it in the case.

    The outbound Message-ID is stored on the ticket so the user's next reply
    threads back onto the same case. The reply itself is appended to
    ``suggestion.messages`` (direction ``out``) so it shows in the admin UI.

    ``case`` is the support-ticket document (dict) from MongoDB.

    Returns the generated Message-ID.
    """
    mongo = DatabaseManager().get_instance().get_db()
    ticket_meta = (case.get("meta") or {}).get("ticket", {})
    ticket_label = f"#{case.get('running_num')}"
    original_subject = ticket_meta.get("subject") or (case.get("suggestion") or {}).get("subject") or "tukipyyntö"
    subject = f"Re: {original_subject}"
    message_id = _new_outbound_message_id()
    in_reply_to = ticket_meta.get("message_id")

    extra_headers = {"Message-ID": message_id}
    if in_reply_to:
        extra_headers["In-Reply-To"] = in_reply_to
        extra_headers["References"] = in_reply_to

    email_sender.queue_email(
        template_name="customer_support/ticket_admin_reply.html",
        subject=subject,
        recipients=[reply_to],
        sender=_ticket_sender(config),
        extra_headers=extra_headers,
        context={
            "ticket_id": ticket_label,
            "message": message,
            "admin_name": admin_label,
        },
    )

    now = utcnow()
    mongo.cases.update_one(
        {"_id": case["_id"]},
        {
            "$push": {
                "suggestion.messages": {
                    "timestamp": now,
                    "message_id": message_id,
                    "from_email": getattr(config, "TICKET_IMAP_USERNAME", ""),
                    "from_name": admin_label,
                    "direction": "out",
                    "subject": subject,
                    "message": message,
                    "status": "queued",
                }
            },
            "$addToSet": {"meta.ticket.reply_message_ids": message_id},
            "$set": {"updated_at": now},
        },
    )
    logger.info("Queued admin reply to %s (%s)", reply_to, ticket_label)
    return message_id


def poll_once(config=Config, db=None, email_sender=None) -> Dict[str, Any]:
    """Run one ingress pass. Returns a summary dict for job logging."""
    config = config() if isinstance(config, type) else config
    if not getattr(config, "TICKET_INGRESS_ENABLED", False):
        return {"skipped": True, "reason": "TICKET_INGRESS_ENABLED is false"}

    server = getattr(config, "TICKET_IMAP_SERVER", "")
    port = int(getattr(config, "TICKET_IMAP_PORT", 993))
    use_ssl = bool(getattr(config, "TICKET_IMAP_USE_SSL", True))
    username = getattr(config, "TICKET_IMAP_USERNAME", "")
    password = getattr(config, "TICKET_IMAP_PASSWORD", "")
    mailbox = getattr(config, "TICKET_IMAP_MAILBOX", "INBOX")

    if not username or not password:
        logger.warning("Support ticket IMAP credentials are not configured.")
        return {"skipped": True, "reason": "IMAP credentials missing"}

    db = db or DatabaseManager().get_instance().get_db()
    email_sender = email_sender or EmailSender(config)

    # Load the admin blocklist once per pass to keep processing consistent.
    blocklist = _load_blocklist(db)

    created = 0
    urgent = 0
    failed = 0

    try:
        if use_ssl:
            client = imaplib.IMAP4_SSL(server, port)
        else:
            client = imaplib.IMAP4(server, port)
        try:
            client.login(username, password)
            client.select(mailbox)
            _, data = client.search(None, "UNSEEN")
            ids = (data[0] or b"").split()
            logger.info("Support ticket ingress: %s unseen messages", len(ids))
            for num in ids:
                try:
                    _, msg_data = client.fetch(num, "(RFC822)")
                    raw = msg_data[0][1]
                    running_num = _process_email(raw, db, email_sender, config, blocklist=blocklist)
                    if running_num:
                        created += 1
                        # Re-read the case to know if it was urgent
                        case_doc = db.cases.find_one(
                            {"type": "support_ticket", "running_num": running_num}
                        )
                        if case_doc and (case_doc.get("meta") or {}).get("urgent"):
                            urgent += 1
                    # Always mark as seen so we don't reprocess next run.
                    client.store(num, "+FLAGS", "\\Seen")
                except Exception as e:
                    failed += 1
                    logger.exception("Failed processing support ticket email %s", num)
        finally:
            try:
                client.logout()
            except Exception:
                pass
    except Exception as e:
        logger.exception("Support ticket IMAP connection failed")
        raise

    return {"created": created, "urgent": urgent, "failed": failed}


def main():
    result = poll_once()
    logger.info(
        "Support ticket ingress finished: %s created, %s urgent, %s failed",
        result.get("created", 0),
        result.get("urgent", 0),
        result.get("failed", 0),
    )


if __name__ == "__main__":
    main()