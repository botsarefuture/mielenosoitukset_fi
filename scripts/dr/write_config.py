#!/usr/bin/env python3
"""Generate fresh sandbox configuration; never read production secrets."""
import argparse
import json
import os
from pathlib import Path
import secrets


def configuration():
    return {
        "SECRET_KEY": secrets.token_urlsafe(48),
        "MONGO_URI": "mongodb://127.0.0.1:27017/?directConnection=true",
        "MONGO_DBNAME": "mielenosoitukset",
        "DEBUG": False,
        "TESTING": False,
        "SERVER_NAME": "pentest.mielenosoitukset.fi",
        "PREFERRED_URL_SCHEME": "https",
        "SESSION_COOKIE_SECURE": True,
        "ENABLE_EMAIL_WORKER": False,
        "ENABLE_BACKGROUND_JOBS": False,
        "DISABLE_BACKGROUND_JOBS": True,
        "ENABLE_PANIC_THREAD": False,
        "TICKET_INGRESS_ENABLED": False,
        "TICKET_IMAP_SERVER": "127.0.0.1",
        "UI_TRANSLATION_SYNC_ENABLED": False,
        "UI_TRANSLATION_GITHUB_AUTO_MERGE": False,
        "GEOCODE_API_KEY": "sandbox-disabled",
        "ADMIN_EMAIL": "reviewer@example.invalid",
        "TICKET_URGENT_TO": "reviewer@example.invalid",
        "ENFORCE_RATELIMIT": True,
        "ENABLE_CHAT": False,
        "SOCKETIO_MESSAGE_QUEUE": "redis://127.0.0.1:6379/0",
        "REDIS_HOST": "127.0.0.1",
        "CACHE_TYPE": "SimpleCache",
        "WEBAUTHN_RP_ID": "pentest.mielenosoitukset.fi",
        "WEBAUTHN_RP_NAME": "Mielenosoitukset TEST / DR",
        "WEBAUTHN_ORIGIN": "https://pentest.mielenosoitukset.fi",
        "CDN_BASE_URL": "https://pentest.mielenosoitukset.fi/media",
        "S3": {
            "ACCESS_KEY": "sandbox-only",
            "SECRET_KEY": secrets.token_urlsafe(32),
            "ENDPOINT_URI": "http://127.0.0.1:5003",
            "BUCKET": "mielenosoitukset.fi",
        },
        "MAIL": {
            "SERVER": "127.0.0.1", "PORT": 1025, "USE_TLS": False,
            "USERNAME": "sandbox", "PASSWORD": secrets.token_urlsafe(24),
            "DEFAULT_SENDER": "sandbox@example.invalid",
        },
    }


def write_config(path):
    # Refuse to rotate session/mail credentials during a rerun.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(configuration(), stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    write_config(parser.parse_args().output)
