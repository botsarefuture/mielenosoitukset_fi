"""Focused coverage for Markdown in administrator support-ticket replies."""

from email import message_from_string

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

from mielenosoitukset_fi.scripts.process_support_tickets import queue_admin_reply
from mielenosoitukset_fi.utils.content_formatting import (
    markdown_to_html,
    markdown_to_plain_text,
)


def test_support_reply_markdown_formats_html_and_plain_text():
    source = """# Tilannepäivitys

**Tärkeä** ja *kiireellinen* huomio.
Toinen rivi.

- Ensimmäinen
- Toinen

1. Tarkista tiedot
2. Vastaa viestiin

Lisätiedot löytyvät [sivustolta](https://mielenosoitukset.fi).
"""

    rendered = markdown_to_html(source)
    plain = markdown_to_plain_text(source)

    assert "<h1>Tilannepäivitys</h1>" in rendered
    assert "<strong>Tärkeä</strong>" in rendered
    assert "<em>kiireellinen</em>" in rendered
    assert "huomio.<br>\nToinen rivi." in rendered
    assert "<ul>" in rendered and "<li>Ensimmäinen</li>" in rendered
    assert "<ol>" in rendered and "<li>Tarkista tiedot</li>" in rendered
    assert '<a href="https://mielenosoitukset.fi">sivustolta</a>' in rendered

    assert "#" not in plain
    assert "**" not in plain
    assert "*kiireellinen*" not in plain
    assert "- Ensimmäinen" in plain
    assert "1. Tarkista tiedot" in plain
    assert "sivustolta (https://mielenosoitukset.fi)" in plain
    assert "Toinen rivi." in plain


def test_support_reply_markdown_blocks_active_content_and_unsafe_links():
    source = """<script>alert(1)</script>

<img src=x onerror=alert(2)>

<iframe src="https://evil.example"></iframe>
<form action="https://evil.example"><input name="secret"></form>
<svg><script>alert(4)</script></svg>

[javascript link](javascript:alert(3))
[data link](data:text/html;base64,PHNjcmlwdD4=)

[safe link](mailto:support@example.test)
"""

    rendered = markdown_to_html(source)

    assert "<script" not in rendered
    assert "<img" not in rendered
    assert "javascript:" not in rendered
    assert "data:text/html" not in rendered
    assert "<iframe" not in rendered
    assert "<form" not in rendered
    assert "<svg" not in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
    assert "&lt;img src=x onerror=alert(2)&gt;" in rendered
    assert '<a href="mailto:support@example.test">safe link</a>' in rendered


def test_admin_reply_keeps_existing_template_and_has_distinct_multipart_bodies(db):
    case = {
        "_id": db.cases.insert_one({"type": "support_ticket"}).inserted_id,
        "running_num": 100321,
        "suggestion": {"subject": "Testitukipyyntö"},
        "meta": {"ticket": {"message_id": "<original@example.test>"}},
    }
    captured = {}

    class CapturingSender:
        def queue_email(self, **kwargs):
            captured.update(kwargs)

    queue_admin_reply(
        CapturingSender(),
        {"TICKET_SENDER": "support@example.test"},
        case,
        reply_to="recipient@example.test",
        message="**Hei!**\n\nKatso [ohje](https://mielenosoitukset.fi/ohje).",
        admin_label="ylläpitäjä",
    )

    assert captured["template_name"] == "customer_support/ticket_admin_reply.html"
    assert isinstance(captured["context"]["message_html"], Markup)
    assert "<strong>Hei!</strong>" in captured["context"]["message_html"]
    assert "**Hei!**" not in captured["plain_body"]
    assert "ohje (https://mielenosoitukset.fi/ohje)" in captured["plain_body"]

    environment = Environment(
        loader=FileSystemLoader("mielenosoitukset_fi/templates/emails")
    )
    html = environment.get_template(captured["template_name"]).render(
        captured["context"]
    )
    assert "Vastaus tukipyyntöösi #100321" in html
    assert '<div class="header">' in html
    assert '<div class="footer">' in html
    assert '<div class="message"><p><strong>Hei!</strong></p>' in html
    assert "Vastaa tähän viestiin, jos tarvitset lisäapua." in html


def test_email_sender_uses_plain_override_only_when_explicitly_requested(monkeypatch):
    from mielenosoitukset_fi.emailer.EmailSender import EmailSender

    sender = object.__new__(EmailSender)
    sender._instance_id = "test-instance"
    sender._env = Environment(
        loader=FileSystemLoader("mielenosoitukset_fi/templates/emails")
    )
    queued = []
    sender._queue_collection = type(
        "Queue",
        (),
        {"insert_one": lambda self, document: queued.append(document)},
    )()
    monkeypatch.setattr(sender, "_start_retry_timer", lambda *_args: None)

    sender.queue_email(
        template_name="customer_support/ticket_admin_reply.html",
        subject="Testi",
        recipients=["recipient@example.test"],
        context={"ticket_id": "#1", "message_html": Markup("<p>HTML</p>")},
        plain_body="PLAIN",
    )

    assert queued[0]["body"] == "PLAIN"
    assert "<div class=\"message\"><p>HTML</p></div>" in queued[0]["html"]


def test_support_reply_delivery_is_multipart_plain_and_html(monkeypatch):
    from mielenosoitukset_fi.emailer.EmailJob import EmailJob, Sender
    from mielenosoitukset_fi.emailer.EmailSender import EmailSender

    delivered = []

    class FakeSMTP:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def starttls(self):
            pass

        def login(self, *_args):
            pass

        def sendmail(self, _sender, _recipients, raw_message):
            delivered.append(message_from_string(raw_message))

    email_sender = object.__new__(EmailSender)
    email_sender._mailer_name = "Test"
    email_sender._mailer_version = "1"
    email_sender._logger = type("Logger", (), {"error": lambda *_args: None})()
    monkeypatch.setattr(
        email_sender,
        "_delivery_settings",
        lambda _sender: {
            "sender_address": "support@example.test",
            "smtp_server": "smtp.example.test",
            "smtp_port": 587,
            "smtp_username": "support@example.test",
            "smtp_password": "secret",
            "use_tls": True,
        },
    )
    monkeypatch.setattr("smtplib.SMTP", FakeSMTP)

    email_sender.send_email(
        EmailJob(
            subject="Testi",
            recipients=["recipient@example.test"],
            body="PLAIN REPLY",
            html="<html><body><strong>HTML REPLY</strong></body></html>",
            sender=Sender(profile="ticket", email_address="support@example.test"),
        ),
        raise_on_error=True,
    )

    assert len(delivered) == 1
    parts = {part.get_content_type(): part for part in delivered[0].walk()}
    assert parts["text/plain"].get_payload(decode=True).decode() == "PLAIN REPLY"
    assert "<strong>HTML REPLY</strong>" in parts["text/html"].get_payload(
        decode=True
    ).decode()
