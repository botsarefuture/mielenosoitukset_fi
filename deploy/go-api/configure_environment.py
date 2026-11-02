#!/usr/bin/env python3
"""Copy the authorized production DB settings without printing credential values."""
import json
import hashlib
import hmac
import os
from pathlib import Path
import tempfile
import yaml


def configure(source, target):
    config = yaml.safe_load(Path(source).read_text())
    values = {"MONGODB_URI": config.get("MONGO_URI"), "MONGODB_DATABASE": config.get("MONGO_DBNAME"), "API_ADDR": "127.0.0.1:8091"}
    # Existing local Redis; isolated application keys, no global Redis changes.
    # An empty explicit value opts out and keeps the in-process caches only.
    redis_url = config.get("GO_PUBLIC_REDIS_URL", "redis://127.0.0.1:6379/0")
    if not isinstance(redis_url, str) or any(c in redis_url for c in "\n\r\0"):
        raise ValueError("Invalid GO_PUBLIC_REDIS_URL")
    if redis_url:
        values["PUBLIC_REDIS_URL"] = redis_url
    # Writes require an explicit rollout switch. Derive a separate key; Go
    # cannot use this value to validate Flask sessions or mint authentication.
    if config.get("GO_SUBMIT_ENABLED") is True:
        secret = config.get("SECRET_KEY")
        if not isinstance(secret, str) or len(secret) < 32:
            raise ValueError("A strong SECRET_KEY is required for Go submission intake")
        values["PUBLIC_SUBMIT_SECRET"] = hmac.new(
            secret.encode(), b"moso-go-submission-rate-v1", hashlib.sha256,
        ).hexdigest()
        values["PUBLIC_SUBMIT_ORIGIN"] = config.get("GO_SUBMIT_ORIGIN", "https://mielenosoitukset.fi")
        values["PUBLIC_SUBMIT_SESSION_SOCKET"] = "/var/www/mielenosoitukset_fi/mielenosoitus.sock"
        babel = config.get("BABEL") or {}
        values["PUBLIC_SUBMIT_LOCALES"] = ",".join(babel.get("SUPPORTED_LOCALES", ["fi", "en"]) or ["fi"])
    for key, value in values.items():
        if not isinstance(value, str) or not value or any(c in value for c in "\n\r\0"):
            raise ValueError(f"Missing or invalid {key}; refusing to guess production settings")
    target = Path(target)
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=target.parent, delete=False) as file:
        temporary = Path(file.name)
        try:
            os.fchmod(file.fileno(), 0o600)
            for key, value in values.items():
                file.write(f"{key}={json.dumps(value, ensure_ascii=False)}\n")
            file.flush()
            os.fsync(file.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("target")
    args = parser.parse_args()
    configure(args.source, args.target)
    print("API environment installed with mode0600; credential values were not printed")
