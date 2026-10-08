from types import SimpleNamespace

import smtplib

from config import Config
from mielenosoitukset_fi.emailer.EmailJob import Sender
from mielenosoitukset_fi.emailer.EmailSender import EmailSender, _sanitize_delivery_error
from mielenosoitukset_fi.scripts import process_support_tickets
from mielenosoitukset_fi.scripts.process_support_tickets import (
    _should_queue_auto_reply,
    _ticket_sender,
)


def test_ticket_sender_profile_does_not_persist_smtp_credentials(monkeypatch):
    monkeypatch.setattr(Config, "TICKET_SENDER", "support@example.test")
    sender = _ticket_sender({})

    assert sender.profile == "ticket"
    assert sender.email_address == "support@example.test"
    assert sender.to_dict() == {
        "profile": "ticket",
        "email_address": "support@example.test",
    }


def test_ticket_sender_reads_flask_mapping_without_attribute_access(monkeypatch):
    monkeypatch.setattr(Config, "TICKET_SENDER", "fallback@example.test")

    sender = _ticket_sender({"TICKET_SENDER": "mapped@example.test"})

    assert sender.email_address == "mapped@example.test"


def test_ticket_profile_resolves_delivery_settings_from_server_config():
    email_sender = object.__new__(EmailSender)
    email_sender._config = SimpleNamespace(
        TICKET_SMTP_SERVER="smtp.example.test",
        TICKET_SMTP_PORT=587,
        TICKET_SMTP_USE_TLS=True,
        TICKET_IMAP_USERNAME="support-login@example.test",
        TICKET_IMAP_PASSWORD="secret",
        TICKET_SENDER="support@example.test",
    )

    settings = email_sender._delivery_settings(Sender(profile="ticket"))

    assert settings == {
        "sender_address": "support@example.test",
        "smtp_server": "smtp.example.test",
        "smtp_port": 587,
        "smtp_username": "support-login@example.test",
        "smtp_password": "secret",
        "use_tls": True,
    }


def test_legacy_empty_ticket_sender_is_recovered_from_server_config():
    email_sender = object.__new__(EmailSender)
    email_sender._config = SimpleNamespace(
        TICKET_SMTP_SERVER="smtp.example.test",
        TICKET_SMTP_PORT=587,
        TICKET_SMTP_USE_TLS=True,
        TICKET_IMAP_USERNAME="support-login@example.test",
        TICKET_IMAP_PASSWORD="secret",
        TICKET_SENDER="support@example.test",
    )
    legacy_sender = Sender.from_dict(
        {
            "email_server": "",
            "email_port": 587,
            "username": "",
            "password": "",
            "use_tls": True,
            "email_address": "",
        }
    )

    settings = email_sender._delivery_settings(legacy_sender)

    assert settings["smtp_server"] == "smtp.example.test"
    assert settings["smtp_username"] == "support-login@example.test"
    assert settings["sender_address"] == "support@example.test"


def test_null_ticket_smtp_overrides_use_safe_defaults():
    class TicketConfig(Config):
        pass

    TicketConfig._apply_config(
        {
            "TICKET_IMAP_SERVER": "mail.example.test",
            "TICKET_SMTP_SERVER": None,
            "TICKET_SMTP_PORT": None,
            "TICKET_SMTP_USE_TLS": None,
        }
    )

    assert TicketConfig.TICKET_SMTP_SERVER == "mail.example.test"
    assert TicketConfig.TICKET_SMTP_PORT == 587
    assert TicketConfig.TICKET_SMTP_USE_TLS is True


def test_delivery_error_sanitizer_redacts_recipient_addresses():
    error = smtplib.SMTPRecipientsRefused(
        {"victim@example.test": (550, b"No such user here")}
    )

    sanitized = _sanitize_delivery_error(error)

    assert "victim@example.test" not in sanitized
    assert "[redacted]" in sanitized
    assert "No such user here" in sanitized


def test_support_auto_reply_is_disabled_by_default():
    config = SimpleNamespace()

    assert not _should_queue_auto_reply(config)


def test_support_auto_reply_requires_explicit_opt_in():
    config = SimpleNamespace(TICKET_AUTO_REPLY_ENABLED=True)

    assert _should_queue_auto_reply(config)


def test_support_auto_reply_respects_explicit_disable():
    config = SimpleNamespace(TICKET_AUTO_REPLY_ENABLED=False)

    assert not _should_queue_auto_reply(config)


def _process_new_ticket(monkeypatch, *, from_wrapper):
    parsed = {
        "message_id": "<incoming@example.test>",
        "in_reply_to": None,
        "references": None,
        "subject": "Test request",
        "from_header": "Visitor <visitor@example.test>",
        "sender_name": "Visitor",
        "sender_email": "visitor@example.test",
        "body": "Test request",
        "html_body": "<p>Test request</p>",
        "urgent": False,
        "from_wrapper": from_wrapper,
    }
    monkeypatch.setattr(process_support_tickets, "_parse_message", lambda *_args: parsed)
    monkeypatch.setattr(
        process_support_tickets.Case,
        "create_new",
        lambda **_kwargs: SimpleNamespace(running_num=100500, _id="case-id"),
    )

    class Cases:
        def find_one(self, *_args, **_kwargs):
            return None

        def update_one(self, *_args, **_kwargs):
            return None

    class EmailSender:
        def __init__(self):
            self.queued = []

        def queue_email(self, **kwargs):
            self.queued.append(kwargs)

    mongo = SimpleNamespace(cases=Cases())
    email_sender = EmailSender()
    config = SimpleNamespace(
        TICKET_IMAP_USERNAME="support@mielenosoitukset.test",
        TICKET_SENDER="support@mielenosoitukset.test",
        MAIL_DEFAULT_SENDER="no-reply@mielenosoitukset.test",
        TICKET_AUTO_REPLY_ENABLED=False,
        TICKET_SLA_HOURS=48,
        TICKET_URGENT_KEYWORD="URGENT",
    )

    result = process_support_tickets._process_email(
        b"ignored",
        mongo,
        email_sender,
        config,
        blocklist=[],
    )
    return result, email_sender.queued


def test_wrapper_ticket_does_not_queue_external_acknowledgement(monkeypatch):
    result, queued = _process_new_ticket(monkeypatch, from_wrapper=True)

    assert result == 100500
    assert queued == []


def test_direct_mail_does_not_queue_external_acknowledgement(monkeypatch):
    result, queued = _process_new_ticket(monkeypatch, from_wrapper=False)

    assert result == 100500
    assert queued == []
