"""Seed development data for docker-compose environments.

This script waits for MongoDB to be reachable, then inserts:
- An admin user with username/password admin.
- A handful of demonstration documents to make the UI usable in development.

The script is idempotent: rerunning it will not duplicate entries.
"""

from __future__ import annotations

import logging
import os
import socket
import time
from datetime import datetime, timedelta
from typing import Tuple

import yaml
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
from pymongo.uri_parser import parse_uri
from werkzeug.security import generate_password_hash

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger("dev_seed")

CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config.yaml")
DEFAULT_URI = "mongodb://mongo:27017/mielenosoitukset_dev"
DEFAULT_DB = "mielenosoitukset_dev"


def load_config() -> Tuple[str, str]:
    """Load Mongo settings from the YAML config if it exists."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle) or {}
        return config.get("MONGO_URI", DEFAULT_URI), config.get("MONGO_DBNAME", DEFAULT_DB)
    LOGGER.warning("Config file %s not found. Falling back to defaults.", CONFIG_PATH)
    return DEFAULT_URI, DEFAULT_DB


def wait_for_mongo(uri: str, retries: int = 20, delay: int = 5) -> MongoClient:
    """Wait until MongoDB responds to a ping, then return a client."""
    attempt = 0
    while attempt < retries:
        try:
            client = MongoClient(uri, serverSelectionTimeoutMS=3000)
            client.admin.command("ping")
            LOGGER.info("Connected to MongoDB at %s", uri)
            return client
        except ServerSelectionTimeoutError as exc:
            attempt += 1
            LOGGER.info(
                "MongoDB not ready yet (attempt %s/%s): %s. Sleeping %ss",
                attempt,
                retries,
                exc,
                delay,
            )
            time.sleep(delay)
    raise RuntimeError(f"Could not connect to MongoDB at {uri}")


def ensure_hosts_resolve(uri: str) -> None:
    """Validate that the MongoDB hosts in the URI resolve to IPs.

    This provides earlier, clearer feedback if the hostname in the connection
    string is incorrect (e.g., a missing docker-compose service name).
    """

    try:
        parsed = parse_uri(uri)
    except Exception as exc:  # pragma: no cover - defensive logging only
        LOGGER.warning("Could not parse Mongo URI %s for host validation: %s", uri, exc)
        return

    hosts = parsed.get("nodelist") or []
    unresolved = []

    for host, port in hosts:
        try:
            socket.getaddrinfo(host, port, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            unresolved.append((host, port, exc))

    if unresolved:
        details = ", ".join(f"{host}:{port} ({err})" for host, port, err in unresolved)
        raise RuntimeError(
            f"Could not resolve Mongo host(s): {details}. "
            "Check your docker-compose service names or MONGO_URI."
        )

    LOGGER.info("Mongo hosts resolved: %s", ", ".join(f"{h}:{p}" for h, p in hosts))


def seed_admin_user(db) -> None:
    """Create a default admin user if it does not exist."""
    admin_doc = {
        "username": "admin",
        "password_hash": generate_password_hash("admin"),
        "email": "admin@example.com",
        "displayname": "Admin",
        "global_admin": True,
        "confirmed": True,
        "global_permissions": ["admin"],
        "role": "global_admin",
        "banned": False,
        "mfa_enabled": False,
        "followers": [],
        "following": [],
        "created_at": datetime.utcnow(),
        "last_login": None,
    }

    result = db.users.update_one(
        {"username": "admin"}, {"$setOnInsert": admin_doc}, upsert=True
    )
    if result.upserted_id:
        LOGGER.info("Created default admin user (username=admin, password=admin)")
    else:
        LOGGER.info("Admin user already present; skipping creation")


def seed_demonstrations(db) -> None:
    """Insert a handful of sample demonstrations for development."""
    today = datetime.utcnow().date()
    base_events = [
        {
            "title": "Ilmastomarssi keskustassa",
            "description": "Kulkue ilmastotoimien puolesta ja hiilineutraalin Suomen puolesta.",
            "city": "Helsinki",
            "address": "Narinkkatori, Helsinki",
            "date": (today + timedelta(days=3)).strftime("%Y-%m-%d"),
            "start_time": "12:00",
            "end_time": "14:00",
            "event_type": "marssi",
            "route": "Narinkkatori → Eduskuntatalo",
            "tags": ["ilmasto", "marssi"],
            "facebook": "https://example.com/ilmastomarssi",
        },
        {
            "title": "Sananvapauden puolesta",
            "description": "Rauhanomainen kokoontuminen sananvapauden tukemiseksi.",
            "city": "Tampere",
            "address": "Keskustori 1, Tampere",
            "date": (today + timedelta(days=10)).strftime("%Y-%m-%d"),
            "start_time": "17:00",
            "end_time": "18:30",
            "event_type": "mielenosoitus",
            "tags": ["oikeudet", "sananvapaus"],
            "facebook": "https://example.com/sananvapaus",
        },
        {
            "title": "Luonnon monimuotoisuus nyt!",
            "description": "Tilaisuus luonnon monimuotoisuuden ja lähimetsien puolesta.",
            "city": "Turku",
            "address": "Kauppatori, Turku",
            "date": (today + timedelta(days=17)).strftime("%Y-%m-%d"),
            "start_time": "15:00",
            "end_time": "16:30",
            "event_type": "mielenosoitus",
            "tags": ["luonto", "ympäristö"],
            "facebook": "https://example.com/luonto",
        },
    ]

    for idx, demo in enumerate(base_events, start=1):
        slug = demo["title"].lower().replace(" ", "-")
        demo_doc = {
            **demo,
            "approved": True,
            "hide": False,
            "rejected": False,
            "recurs": False,
            "in_past": False,
            "organizers": [
                {"name": "Kehitystiimi", "contact": "dev@example.com"}
            ],
            "aliases": [],
            "running_number": idx,
            "slug": slug,
            "formatted_date": demo["date"],
            "created_datetime": datetime.utcnow(),
            "last_modified": datetime.utcnow(),
            "preview_image": "",
            "cover_picture": "",
            "cover_source": "dev-seed",
        }

        result = db.demonstrations.update_one(
            {"title": demo_doc["title"], "date": demo_doc["date"]},
            {"$setOnInsert": demo_doc},
            upsert=True,
        )
        if result.upserted_id:
            LOGGER.info("Inserted demonstration '%s' on %s", demo_doc["title"], demo_doc["date"])
        else:
            LOGGER.info("Demonstration '%s' already present; skipping", demo_doc["title"])


def main() -> None:
    uri, dbname = load_config()
    ensure_hosts_resolve(uri)
    client = wait_for_mongo(uri)
    db = client[dbname]

    seed_admin_user(db)
    seed_demonstrations(db)

    LOGGER.info("Development data ready: admin + demo events available")


if __name__ == "__main__":
    main()
