import re
import threading
import smtplib
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from jinja2 import Environment, FileSystemLoader
from mielenosoitukset_fi.database_manager import DatabaseManager
from .EmailJob import EmailJob
import time
import uuid
import pymongo
from config import Config
from mielenosoitukset_fi.utils.logger import logger

EMAIL_MAX_ATTEMPTS = 30
EMAIL_RETRY_COOLDOWN_SECONDS = 60
EMAIL_STALE_IN_FLIGHT_SECONDS = 600
EMAIL_SMTP_TIMEOUT_SECONDS = 30

# Redact email addresses from errors persisted for admins: SMTP exception
# strings (e.g. ``SMTPRecipientsRefused``) echo the rejected recipient
# addresses, which must not end up in Admin → System status.
_EMAIL_ADDRESS_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def _sanitize_delivery_error(error):
    """Return a short, recipient-safe summary of a delivery failure."""
    return _EMAIL_ADDRESS_RE.sub("[redacted]", str(error))[:500]

# Only one in-process queue worker per Python process. Several modules create
# module-level EmailSender singletons; spawning a polling thread for each
# would produce many threads all claiming the same queue.
_WORKER_STARTED = False


class EmailSender:
    """The EmailSender class handles sending emails by processing email jobs from a queue.
    It uses SMTP to send emails and supports templated email content.
    """

    def __init__(self, config=Config):
        self._config = config() if isinstance(config, type) else config
        self._db_manager = DatabaseManager().get_instance()
        self._db = self._db_manager.get_db()
        self._queue_collection = self._db["email_queue"]
        self._cases_collection = self._db["cases"]
        self._env = Environment(
            loader=FileSystemLoader("mielenosoitukset_fi/templates/emails")
        )
        self._logger = logger
        self._mailer_name = getattr(self._config, "MAILER_NAME", "MielenosoituksetMail")
        self._mailer_version = getattr(self._config, "MAILER_VERSION", "1.0")

        # unique instance id for scoping jobs
        self._instance_id = str(uuid.uuid4())

        if getattr(self._config, "ENABLE_EMAIL_WORKER", True):
            self.start_worker()

    def start_worker(self):
        global _WORKER_STARTED
        if _WORKER_STARTED:
            return
        _WORKER_STARTED = True
        worker_thread = threading.Thread(
            target=self.process_queue,
            name=f"email-worker-{self._instance_id[:8]}",
            daemon=True,
        )
        worker_thread.start()

    @staticmethod
    def _start_retry_timer(delay_seconds, func, args):
        timer = threading.Timer(delay_seconds, func, args)
        timer.daemon = True
        timer.start()

    def process_queue(self):
        """Claim and send jobs globally (not instance-scoped).

        Uses atomic ``find_one_and_update`` to claim one pending or failed
        job at a time.  On success the document is deleted; on failure it is
        marked ``status="failed"`` so the periodic ``process_email_queue``
        background job can retry it later.
        """
        while True:
            job_doc = self._claim_next_job()
            if job_doc:
                self._process_claimed_job(job_doc)
            time.sleep(5)

    def _claim_next_job(self):
        """Atomically claim the next eligible job (pending or retryable).

        Returns the claimed document dict or ``None``.
        """
        cooldown_cutoff = datetime.now(timezone.utc) - timedelta(seconds=EMAIL_RETRY_COOLDOWN_SECONDS)

        return self._queue_collection.find_one_and_update(
            {
                "$and": [
                    {"status": {"$in": [None, "pending", "failed"]}},
                    {
                        "$or": [
                            {"attempts": {"$exists": False}},
                            {"attempts": {"$lt": EMAIL_MAX_ATTEMPTS}},
                        ]
                    },
                    {
                        "$or": [
                            {"status": {"$ne": "failed"}},
                            {"last_attempt_at": {"$lte": cooldown_cutoff}},
                        ]
                    },
                ]
            },
            {
                "$set": {
                    "status": "in_flight",
                    "claimed_at": datetime.now(timezone.utc),
                    "claimed_by": self._instance_id[:8],
                },
                "$inc": {"attempts": 1},
            },
            sort=[("_id", 1)],
            return_document=pymongo.ReturnDocument.AFTER,
        )

    def _process_claimed_job(self, job_doc):
        """Send a claimed job, updating status on success/failure."""
        email_job = EmailJob.from_dict(job_doc)
        try:
            self.send_email(email_job, raise_on_error=True)
            self._queue_collection.delete_one({"_id": job_doc["_id"]})
            self._record_cases_delivery(job_doc, delivered=True)
        except Exception as exc:
            self._record_delivery_failure(job_doc, exc)

    def _requeue_stale_in_flight(self):
        """Mark jobs stuck ``in_flight`` (e.g. worker crashed) as ``failed``."""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=EMAIL_STALE_IN_FLIGHT_SECONDS)
        self._queue_collection.update_many(
            {"status": "in_flight", "claimed_at": {"$lte": cutoff}},
            {
                "$set": {
                    "status": "failed",
                    "last_error": "stale claim (worker crashed/restarted)",
                    "last_attempt_at": datetime.now(timezone.utc),
                },
            },
        )

    def _reopen_exhausted_legacy_ticket_jobs(self):
        """Reset exhausted legacy empty-sender ticket jobs so they retry.

        Pre-fix support replies were queued with empty SMTP fields, so their
        sender has nothing to resolve. If the broken configuration lasted
        longer than the retry budget those jobs reached ``EMAIL_MAX_ATTEMPTS``
        and ``_claim_next_job`` now skips them forever. Reset the attempt
        counter so the config-based recovery in ``_delivery_settings`` gets a
        chance to deliver them.
        """
        self._queue_collection.update_many(
            {
                "status": "failed",
                "attempts": {"$gte": EMAIL_MAX_ATTEMPTS},
                "sender": {"$type": "object"},
                "sender.email_server": {"$in": [None, ""]},
                "sender.profile": {"$ne": "ticket"},
            },
            {"$set": {"attempts": 0}},
        )

    def _record_cases_delivery(self, job_doc, delivered, error=None):
        """Update the delivery status on matching support-ticket case messages.

        Looks up the ``Message-ID`` header from the queued email and, if it
        matches a support ticket's ``meta.ticket.reply_message_ids``, updates
        the corresponding ``suggestion.messages`` entry with the delivery
        status so the admin UI can show it.
        """
        message_id = (job_doc.get("extra_headers") or {}).get("Message-ID")
        if not message_id:
            return
        status = "sent" if delivered else "failed"
        set_fields = {"suggestion.messages.$[m].status": status}
        if delivered:
            set_fields["suggestion.messages.$[m].sent_at"] = datetime.now(timezone.utc)
        else:
            set_fields["suggestion.messages.$[m].error"] = (error or "unknown")[:500]

        try:
            self._cases_collection.update_many(
                {
                    "meta.ticket.reply_message_ids": message_id,
                    "suggestion.messages": {"$exists": True, "$ne": None},
                },
                {"$set": set_fields},
                array_filters=[{"m.message_id": message_id}],
            )
        except Exception:
            self._logger.debug(
                "Could not update case delivery status for Message-ID %s",
                message_id,
                exc_info=True,
            )

    def _record_delivery_failure(self, job_doc, error):
        """Persist retry state, case status, and a sanitized admin error."""
        error_str = _sanitize_delivery_error(error)
        now = datetime.now(timezone.utc)
        self._queue_collection.update_one(
            {"_id": job_doc["_id"]},
            {
                "$set": {
                    "status": "failed",
                    "last_error": error_str,
                    "last_attempt_at": now,
                }
            },
        )
        self._record_cases_delivery(job_doc, delivered=False, error=error_str)
        try:
            sender = job_doc.get("sender") or {}
            self._db["admin_logs"].update_one(
                {
                    "event": "email_delivery_failed",
                    "details.job_id": str(job_doc.get("_id")),
                },
                {
                    "$set": {
                        "event": "email_delivery_failed",
                        "module": "emailer",
                        "level": "error",
                        "timestamp": now,
                        "details": {
                            "job_id": str(job_doc.get("_id")),
                            "error": error_str,
                            "attempts": job_doc.get("attempts", 0),
                            "recipient_count": len(job_doc.get("recipients") or []),
                            "sender_profile": sender.get("profile") or "legacy",
                        },
                    }
                },
                upsert=True,
            )
        except Exception:
            self._logger.debug(
                "Could not record email delivery failure in admin status",
                exc_info=True,
            )

    def _config_value(self, key, default=None):
        """Read config from either an object or mapping, then canonical Config."""
        if hasattr(self._config, "get"):
            value = self._config.get(key)
        else:
            value = getattr(self._config, key, None)
        if value is None or value == "":
            value = getattr(Config, key, default)
        return default if value is None or value == "" else value

    def _delivery_settings(self, sender):
        """Resolve SMTP settings, including legacy empty ticket senders."""
        is_ticket = bool(
            sender
            and (
                getattr(sender, "profile", None) == "ticket"
                or not getattr(sender, "email_server", None)
            )
        )
        if is_ticket:
            smtp_server = self._config_value(
                "TICKET_SMTP_SERVER",
                self._config_value(
                    "TICKET_IMAP_SERVER", self._config_value("MAIL_SERVER")
                ),
            )
            smtp_port = int(self._config_value("TICKET_SMTP_PORT", 587))
            smtp_username = self._config_value(
                "TICKET_IMAP_USERNAME", self._config_value("MAIL_USERNAME", "")
            )
            smtp_password = self._config_value(
                "TICKET_IMAP_PASSWORD", self._config_value("MAIL_PASSWORD", "")
            )
            sender_address = (
                getattr(sender, "email_address", None)
                or self._config_value("TICKET_SENDER", smtp_username)
            )
            use_tls = bool(self._config_value("TICKET_SMTP_USE_TLS", True))
        elif sender:
            sender_address = sender.email_address
            smtp_server = sender.email_server
            smtp_port = int(sender.email_port)
            smtp_username = sender.username
            smtp_password = sender.password
            use_tls = bool(sender.use_tls)
        else:
            sender_address = self._config_value("MAIL_DEFAULT_SENDER")
            smtp_server = self._config_value("MAIL_SERVER")
            smtp_port = int(self._config_value("MAIL_PORT", 587))
            smtp_username = self._config_value("MAIL_USERNAME", "")
            smtp_password = self._config_value("MAIL_PASSWORD", "")
            use_tls = bool(self._config_value("MAIL_USE_TLS", True))

        if not smtp_server:
            raise ValueError("SMTP server is not configured")
        if not sender_address:
            raise ValueError("Email sender address is not configured")
        return {
            "sender_address": sender_address,
            "smtp_server": smtp_server,
            "smtp_port": smtp_port,
            "smtp_username": smtp_username,
            "smtp_password": smtp_password,
            "use_tls": use_tls,
        }

    def send_email(self, email_job, raise_on_error=False):
        try:
            settings = self._delivery_settings(email_job.sender)
            sender_address = settings["sender_address"]
            smtp_server = settings["smtp_server"]
            smtp_port = settings["smtp_port"]
            smtp_username = settings["smtp_username"]
            smtp_password = settings["smtp_password"]
            use_tls = settings["use_tls"]

            has_attachments = bool(getattr(email_job, "attachments", []))
            if has_attachments:
                msg = MIMEMultipart("mixed")
                alt_part = MIMEMultipart("alternative")
            else:
                msg = MIMEMultipart("alternative")
                alt_part = msg

            # Standard headers
            msg["Subject"] = email_job.subject
            msg["From"] = sender_address
            msg["To"] = ", ".join(email_job.recipients)
            msg["X-Mailer"] = f"{self._mailer_name}/{self._mailer_version}"

            # Extra headers from job
            for key, value in (email_job.extra_headers or {}).items():
                msg[key] = value

            # Body
            if email_job.body:
                alt_part.attach(MIMEText(email_job.body, "plain"))
            if email_job.html:
                alt_part.attach(MIMEText(email_job.html, "html"))

            # Attachments
            if has_attachments:
                msg.attach(alt_part)
                for attachment in email_job.attachments:
                    from email.mime.base import MIMEBase
                    from email import encoders

                    maintype, subtype = attachment["mime_type"].split("/")
                    part = MIMEBase(maintype, subtype, name=attachment["filename"])
                    part.set_payload(attachment["content"])
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f'attachment; filename="{attachment["filename"]}"',
                    )
                    if attachment["mime_type"] == "text/calendar":
                        part.add_header(
                            "Content-Type",
                            f'text/calendar; method=REQUEST; charset=UTF-8; name="{attachment["filename"]}"'
                        )
                    else:
                        part.add_header("Content-Type", attachment["mime_type"])
                    msg.attach(part)

            # Send
            with smtplib.SMTP(smtp_server, smtp_port, timeout=EMAIL_SMTP_TIMEOUT_SECONDS) as server:
                if use_tls:
                    server.starttls()
                server.login(smtp_username, smtp_password)
                server.sendmail(sender_address, email_job.recipients, msg.as_string())
            return True

        except Exception as e:
            self._logger.error(f"Failed to send email: {str(e)}")
            if raise_on_error:
                raise
            return False

    def queue_email(
        self, template_name, subject, recipients, context,
        sender=None, attachments=None, extra_headers=None
    ):
        """Queue an email for this instance"""
        template = self._env.get_template(template_name)
        body = template.render(context)
        email_job = EmailJob(
            subject=subject,
            recipients=recipients,
            body=body,
            html=body,
            sender=sender,
            attachments=attachments,
            extra_headers=extra_headers,
            instance_id=self._instance_id,
        )
        retry_attempts = 3

        def attempt_insert(attempt):
            try:
                self._queue_collection.insert_one(email_job.to_dict())
            except Exception as e:
                self._logger.error(f"Failed to queue email: {str(e)}")
                if attempt < retry_attempts - 1:
                    self._logger.info("Retrying in 1 hour...")
                    self._start_retry_timer(3600, attempt_insert, [attempt + 1])
                else:
                    self._logger.error("Max retry attempts reached. Email not queued.")

        attempt_insert(0)

    def send_now(
        self, template_name, subject, recipients, context,
        sender=None, attachments=None, extra_headers=None, raise_on_error=False
    ):
        """Send email immediately without queueing"""
        template = self._env.get_template(template_name)
        body = template.render(context)
        email_job = EmailJob(
            subject=subject,
            recipients=recipients,
            body=body,
            html=body,
            sender=sender,
            attachments=attachments,
            extra_headers=extra_headers,
            instance_id=self._instance_id,
        )

        if raise_on_error:
            return self.send_email(email_job, raise_on_error=True)

        retry_attempts = 3

        def attempt_send(attempt):
            try:
                self.send_email(email_job)
            except Exception as e:
                self._logger.error(f"Failed to send email immediately: {str(e)}")
                if attempt < retry_attempts - 1:
                    self._logger.info("Retrying in 1 hour...")
                    self._start_retry_timer(3600, attempt_send, [attempt + 1])
                else:
                    self._logger.error("Max retry attempts reached. Email not sent.")

        attempt_send(0)

    def _die_when_no_jobs(self):
        """Wait until this instance's queue is empty"""
        while self._queue_collection.count_documents({"instance_id": self._instance_id}) > 0:
            time.sleep(1)
        self._logger.info("No email jobs in the queue. Stopping EmailSender.")
        return True
