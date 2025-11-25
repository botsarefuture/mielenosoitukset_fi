#!/usr/bin/env python3

import os
import time
from datetime import datetime
from typing import Tuple

import pytz  # <-- you need to install this: pip install pytz
from bson import ObjectId
from flask import current_app
from pymongo import MongoClient, UpdateOne
from tqdm import tqdm

# ── CONFIG ──────────────────────────────────────────────────────
DEFAULT_MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/mielenosoitukset")
DEFAULT_DB_NAME = os.getenv("MONGO_DBNAME", "mielenosoitukset")
RAW_COLL = "analytics"  # incoming view events
AGGR_COLL = "d_analytics"  # rolled-up analytics
META_COLL = "_meta"  # stores last processed ObjectId
POLL_INTERVAL = 60  # seconds

# ── TIMEZONE SETUP ─────────────────────────────────────────────
HELSINKI_TZ = pytz.timezone("Europe/Helsinki")

def iso_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")

def two(n: int) -> str:
    return f"{n:02d}"

def get_last_seen_id(meta) -> ObjectId:
    doc = meta.find_one({"_id": "analytics_rollup"})
    if doc and "last_seen_id" in doc:
        return doc["last_seen_id"]
    return ObjectId("000000000000000000000000")

def set_last_seen_id(meta, obj_id: ObjectId):
    meta.update_one(
        {"_id": "analytics_rollup"},
        {"$set": {"last_seen_id": obj_id}},
        upsert=True
    )


def _resolve_mongo_settings() -> Tuple[str, str]:
    """Resolve Mongo connection settings from Flask config or environment."""
    uri = DEFAULT_MONGO_URI
    db_name = DEFAULT_DB_NAME

    try:
        app = current_app._get_current_object()
        uri = app.config.get("MONGO_URI", uri)
        db_name = app.config.get("MONGO_DBNAME", db_name)
    except Exception:
        # No app context; fall back to environment defaults
        pass

    return uri, db_name


def _get_collections():
    """Create a Mongo client using the configured settings."""
    uri, db_name = _resolve_mongo_settings()
    client = MongoClient(uri)
    db = client[db_name]
    return client, db[RAW_COLL], db[AGGR_COLL], db[META_COLL]

def rollup_events(run_once: bool = False):
    """
    Process incoming analytics events.

    Parameters
    ----------
    run_once : bool
        If True, process currently available events once and return.
        If False (default), run as a continuous poller (existing behaviour).
    """
    client, raw, aggr, meta = _get_collections()
    last_seen_id = get_last_seen_id(meta)

    try:
        # Single iteration or continuous loop depending on run_once
        while True:
            try:
                new_events = list(
                    raw.find({"_id": {"$gt": last_seen_id}}, {"demo_id": 1, "timestamp": 1})
                       .sort("_id", 1)
                )

                if new_events:
                    counters = {}  # { demo_id: { date: { hour: { minute: count } } } }

                    for ev in new_events:
                        demo_id = ev["demo_id"]
                        ts = ev["timestamp"]
                        if not ts:
                            continue

                        ts_hel = ts.astimezone(HELSINKI_TZ)
                        d = iso_date(ts_hel)
                        h = two(ts_hel.hour)
                        m = two(ts_hel.minute)

                        counters.setdefault(demo_id, {})
                        counters[demo_id].setdefault(d, {})
                        counters[demo_id][d].setdefault(h, {})
                        counters[demo_id][d][h].setdefault(m, 0)
                        counters[demo_id][d][h][m] += 1

                    ops = []
                    for demo_id, dates in counters.items():
                        inc_dict = {}
                        for d, hours in dates.items():
                            for h, minutes in hours.items():
                                for m, count in minutes.items():
                                    inc_dict[f"analytics.{d}.{h}.{m}"] = count

                        ops.append(UpdateOne(
                            {"_id": demo_id},
                            {"$inc": inc_dict},
                            upsert=True
                        ))

                    if ops:
                        aggr.bulk_write(ops, ordered=False)
                        last_seen_id = new_events[-1]["_id"]
                        set_last_seen_id(meta, last_seen_id)

            except Exception:
                # silently ignore errors; optionally log them if needed
                pass

            # If caller requested only a single run, exit now
            if run_once:
                # print with yellow color: run once set
                break

            # Wait until next poll interval (existing behaviour)
            sleep_time = POLL_INTERVAL - (time.time() % POLL_INTERVAL)
            with tqdm(total=int(sleep_time), desc="⏳ Waiting for next roll...", bar_format='{l_bar}{bar}| {remaining}s', ncols=70) as pbar:
                for _ in range(int(sleep_time)):
                    time.sleep(1)
                    pbar.update(1)
    finally:
        client.close()

if __name__ == "__main__":
    rollup_events()
