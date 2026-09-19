from types import SimpleNamespace

from config import Config
from mielenosoitukset_fi.emailer.EmailJob import Sender
from mielenosoitukset_fi.emailer.EmailSender import EmailSender
from mielenosoitukset_fi.scripts.process_support_tickets import _ticket_sender


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
