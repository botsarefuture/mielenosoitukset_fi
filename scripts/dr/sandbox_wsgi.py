"""Deployment wrapper: preserve restored app code, add sandbox-only controls."""
from config import Config
import re
from pathlib import Path
from capture_delivery import delivery_settings
from copy_urls import rewrite

assert Config.MONGO_URI.startswith("mongodb://127.0.0.1:")
assert Config.MAIL_SERVER == "127.0.0.1" and Config.MAIL_PORT == 1025
assert Config.ENDPOINT_URL == "http://127.0.0.1:5003"
if Config.ENABLE_EMAIL_WORKER:
    assert Path("/etc/mielenosoitukset-dr/mail-quarantine.json").is_file()
    assert Config.TICKET_SMTP_SERVER == "127.0.0.1" and Config.TICKET_SMTP_PORT == 1025
    assert Config.TICKET_SMTP_USE_TLS is False
assert Config.ENABLE_BACKGROUND_JOBS is False
assert Config.DISABLE_BACKGROUND_JOBS is True
assert Config.ENABLE_PANIC_THREAD is False
assert Config.TICKET_INGRESS_ENABLED is False

from mielenosoitukset_fi.emailer.EmailSender import EmailSender


def _capture_only_settings(self, sender):
    return delivery_settings(Config, sender)


EmailSender._delivery_settings = _capture_only_settings

from mielenosoitukset_fi.app import create_app

app = create_app({
    "SERVER_NAME": "pentest.mielenosoitukset.fi",
    "PREFERRED_URL_SCHEME": "https",
    "DEBUG": False,
    "ENABLE_BACKGROUND_JOBS": False,
    "DISABLE_BACKGROUND_JOBS": True,
})


@app.after_request
def sandbox_banner(response):
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["X-Environment"] = "pentest-dr"
    if response.is_json and not response.direct_passthrough:
        response.set_data(app.json.dumps(rewrite(response.get_json())))
    if response.mimetype == "text/html" and not response.direct_passthrough:
        banner = ('<aside style="background:#ffe08a;color:#111;padding:16px;font:16px sans-serif">'
                  'TEST / DR COPY — not the live service. Email stays in the test inbox. '
                  'Scheduled jobs and external integrations are disabled.</aside>')
        response.set_data(re.sub(r"(<body\b[^>]*>)", lambda match: match[1] + banner,
                                 rewrite(response.get_data(as_text=True)), count=1, flags=re.I))
    return response
