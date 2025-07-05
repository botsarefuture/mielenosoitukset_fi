#!/usr/bin/env python3

import os
from datetime import datetime
import pytz
from pymongo import MongoClient, UpdateOne
from tqdm import tqdm

# ── CONFIG ──────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI", "mongodb://95.216.148.93:27017")
DB_NAME = "mielenosoitukset"
AGGR_COLL = "d_analytics"

HELSINKI_TZ = pytz.timezone("Europe/Helsinki")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
aggr = db[AGGR_COLL]

def two(n: int) -> str:
    return f"{n:02d}"

def migrate_doc_flat_to_nested(doc):
    old_analytics = doc.get("analytics", {})
    new_analytics = {}

    for flat_key, count in old_analytics.items():
        # flat_key example: "analytics.2024-11-17.19.28"
        parts = flat_key.split(".")
        if len(parts) != 4 or parts[0] != "analytics":
            continue  # skip malformed keys

        day_str, hour_str, minute_str = parts[1], parts[2], parts[3]

        # Parse UTC datetime and convert to Helsinki time
        dt_utc = datetime.strptime(f"{day_str} {hour_str}:{minute_str}", "%Y-%m-%d %H:%M").replace(tzinfo=pytz.UTC)
        dt_hel = dt_utc.astimezone(HELSINKI_TZ)

        d = dt_hel.strftime("%Y-%m-%d")
        h = two(dt_hel.hour)
        m = two(dt_hel.minute)

        if d not in new_analytics:
            new_analytics[d] = {}
        if h not in new_analytics[d]:
            new_analytics[d][h] = {}
        if m not in new_analytics[d][h]:
            new_analytics[d][h][m] = 0

        new_analytics[d][h][m] += count

    return new_analytics

def run_migration(batch_size=100):
    total = aggr.count_documents({})
    print(f"🔄 Migrating {total} documents in batches of {batch_size}...")

    cursor = aggr.find({})
    ops = []
    count_docs = 0

    for doc in tqdm(cursor, total=total):
        new_analytics = migrate_doc_flat_to_nested(doc)

        ops.append(
            UpdateOne(
                {"_id": doc["_id"]},
                {"$set": {"analytics": new_analytics}}
            )
        )
        count_docs += 1

        if len(ops) >= batch_size:
            aggr.bulk_write(ops, ordered=False)
            ops = []

    if ops:
        aggr.bulk_write(ops, ordered=False)

    print(f"✅ Migration complete! Migrated {count_docs} documents.")

if __name__ == "__main__":
    run_migration()
