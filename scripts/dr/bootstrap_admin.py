#!/usr/bin/env python3
"""Create one synthetic review administrator on the sandbox only."""
from datetime import datetime, timezone
import json
from pathlib import Path
import socket

if __name__ == "__main__":
    assert socket.gethostname() == "mielenosoitukset-pentest"
    from config import Config
    from pymongo import MongoClient
    from mielenosoitukset_fi.users.models import User

    assert Config.MONGO_URI.startswith("mongodb://127.0.0.1:")
    credentials = json.loads(Path("/etc/mielenosoitukset-dr/access.json").read_text())
    db = MongoClient(Config.MONGO_URI).mielenosoitukset
    existing = db.users.find_one({"username_canonical": credentials["username"].strip().casefold()})
    if existing:
        assert existing.get("dr_rehearsal_account") is True, "Refusing to replace a restored account"
    else:
        user = User.create_user(credentials["username"], credentials["password"],
                                "reviewer@example.invalid", "DR rehearsal reviewer")
        user.update(global_admin=True, confirmed=True, role="global_admin", dr_rehearsal_account=True)
        identity = db.users.insert_one(user).inserted_id
        db.dr_rehearsal_audit.insert_one({"action": "create_synthetic_review_admin",
                                         "user_id": identity, "at": datetime.now(timezone.utc)})
    print("Synthetic sandbox reviewer ready; credentials remain in the private access file")
