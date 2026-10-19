#!/usr/bin/env python3
"""Quarantine historical sandbox jobs, then enable new mail into local Mailpit.

Run with the app stopped. Keeps every old job and its original status; never
contacts production or processes the production queue.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess

from pymongo import MongoClient


if __name__ == "__main__":
    assert socket.gethostname() == "mielenosoitukset-pentest"
    assert subprocess.run(["systemctl", "is-active", "--quiet", "dr-app"]).returncode != 0
    config_path = Path("/etc/mielenosoitukset-dr/config.yaml")
    config = json.loads(config_path.read_text())
    assert config["MONGO_URI"].startswith("mongodb://127.0.0.1:")
    assert config["MAIL"]["SERVER"] == "127.0.0.1" and config["MAIL"]["PORT"] == 1025
    marker = Path("/etc/mielenosoitukset-dr/mail-quarantine.json")
    if not marker.exists():
        db = MongoClient(config["MONGO_URI"]).mielenosoitukset
        result = db.email_queue.update_many(
            {"dr_original_status": {"$exists": False}},
            [{"$set": {"dr_original_status": {"$ifNull": ["$status", "pending"]},
                        "status": "dr_quarantined", "dr_quarantined_at": datetime.now(timezone.utc)}}],
        )
        marker.write_text(json.dumps({"quarantined_jobs": result.modified_count,
                                      "at": datetime.now(timezone.utc).isoformat()}) + "\n")
        marker.chmod(0o600)
        db.dr_rehearsal_audit.insert_one({"action": "quarantine_restored_email_jobs",
                                         "count": result.modified_count, "at": datetime.now(timezone.utc)})
    config["ENABLE_EMAIL_WORKER"] = True
    config["TICKET_SMTP_SERVER"] = "127.0.0.1"
    config["TICKET_SMTP_PORT"] = 1025
    config["TICKET_SMTP_USE_TLS"] = False
    config["TICKET_IMAP_USERNAME"] = "sandbox"
    config["TICKET_IMAP_PASSWORD"] = config["MAIL"]["PASSWORD"]
    config["TICKET_SENDER"] = "sandbox@example.invalid"
    descriptor = os.open(config_path, os.O_WRONLY | os.O_TRUNC)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(config, stream, indent=2)
        stream.write("\n")
    print("New application email enabled into loopback Mailpit; historical jobs preserved")
