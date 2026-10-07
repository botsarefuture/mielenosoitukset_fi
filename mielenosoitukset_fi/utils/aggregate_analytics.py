#!/usr/bin/env python3

import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from pymongo import MongoClient, UpdateOne
from tqdm import tqdm
import pytz  # <-- you need to install this: pip install pytz
from config import Config

# ── CONFIG ──────────────────────────────────────────────────────
MONGO_URI     = Config.MONGO_URI or "mongodb://localhost:27017"
DB_NAME       = Config.MONGO_DBNAME or "testdb"
RAW_COLL      = "analytics"     # incoming view events
AGGR_COLL     = "d_analytics"   # rolled-up analytics
META_COLL     = "_meta"         # stores last processed ObjectId
POLL_INTERVAL = 60              # seconds
META_ID       = "analytics_rollup"

LOGGER = logging.getLogger(__name__)

# Events written before 2026-01-26 stored the Helsinki wall clock in a
# timezone-naive datetime (pymongo keeps the naive fields and labels them UTC);
# later events store a real UTC instant. The gap between the ObjectId creation
# time and the stored timestamp therefore identifies the legacy shape.
LEGACY_TIMESTAMP_GAP_MIN = 90

# A rebuild waits at most this long for an in-flight rollup pass to finish.
REBUILD_SETTLE_TIMEOUT_S = 30.0

# A pass/rebuild claim older than this is treated as abandoned (its worker
# crashed) and may be taken over by the next caller.
ROLLUP_PASS_STALE_S = 300
REBUILD_STALE_S = 3600

# ── TIMEZONE SETUP ─────────────────────────────────────────────
HELSINKI_TZ = pytz.timezone("Europe/Helsinki")

# ── SETUP ───────────────────────────────────────────────────────
_clients: dict[str, MongoClient] = {}


def _collections():
    """Resolve the collections from the current config (tests reload it)."""
    uri = Config.MONGO_URI or MONGO_URI
    name = Config.MONGO_DBNAME or DB_NAME
    client = _clients.get(uri)
    if client is None:
        client = MongoClient(uri)
        _clients[uri] = client
    database = client[name]
    return database[RAW_COLL], database[AGGR_COLL], database[META_COLL]

def iso_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")

def two(n: int) -> str:
    return f"{n:02d}"

def get_last_seen_id(meta=None) -> ObjectId:
    meta = meta if meta is not None else _collections()[2]
    doc = meta.find_one({"_id": META_ID})
    if doc and "last_seen_id" in doc:
        return doc["last_seen_id"]
    return ObjectId("000000000000000000000000")

def set_last_seen_id(obj_id: ObjectId, meta=None):
    meta = meta if meta is not None else _collections()[2]
    meta.update_one(
        {"_id": META_ID},
        {"$set": {"last_seen_id": obj_id}},
        upsert=True
    )

def get_on_demand_max_ids(meta=None) -> dict[str, ObjectId]:
    meta = meta if meta is not None else _collections()[2]
    doc = meta.find_one({"_id": META_ID}, {"on_demand_max_ids": 1})
    if not doc:
        return {}
    return doc.get("on_demand_max_ids", {}) or {}


def _rollup_is_paused(meta) -> bool:
    """True while a rebuild is rewriting the rolled-up counters."""
    return bool(meta.find_one({"_id": META_ID, "paused": True}, {"_id": 1}))


def _ensure_meta_doc(meta) -> None:
    """Guarantee the coordination document exists before it is claimed."""
    meta.update_one(
        {"_id": META_ID},
        {"$setOnInsert": {"paused": False}},
        upsert=True,
    )


def _claim_pass(meta, owner: str) -> bool:
    """Atomically claim the rollup pass for ``owner``.

    The check-paused and set-in-progress steps are a single atomic update, so
    two workers can never both believe they hold the pass. A missing or stale
    ``pass_started_at`` is treated as abandoned and can be taken over, so a
    crashed worker cannot wedge the rollup forever.
    """
    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(seconds=ROLLUP_PASS_STALE_S)
    claimed = meta.find_one_and_update(
        {"_id": META_ID,
         "paused": {"$ne": True},
         "$or": [
             {"pass_in_progress": {"$ne": True}},
             # Comparison operators never match a missing field, so an absent
             # pass_started_at (legacy/crashed state) must be matched explicitly.
             {"pass_started_at": {"$exists": False}},
             {"pass_started_at": {"$lt": stale_before}},
         ]},
        {"$set": {"pass_in_progress": True, "pass_owner": owner, "pass_started_at": now}},
        upsert=False,
    )
    return claimed is not None


def _release_pass(meta, owner: str) -> None:
    """Release the pass, but only if ``owner`` still holds it."""
    meta.update_one(
        {"_id": META_ID, "pass_owner": owner},
        {"$set": {"pass_in_progress": False}, "$unset": {"pass_owner": ""}},
    )


def _pass_is_live(meta) -> bool:
    """True only while a pass claim is held by someone right now."""
    doc = meta.find_one({"_id": META_ID}, {"pass_in_progress": 1, "pass_started_at": 1})
    if not doc or not doc.get("pass_in_progress"):
        return False
    started = doc.get("pass_started_at")
    if not isinstance(started, datetime):
        # A flag without a timestamp is a half-written/crashed state, not a
        # running pass, so a rebuild may proceed.
        return False
    started = _normalize_timestamp(started)
    return (datetime.now(timezone.utc) - started).total_seconds() < ROLLUP_PASS_STALE_S


def _acquire_rebuild(meta, owner: str) -> bool:
    """Atomically claim the rebuild pause for ``owner``.

    A second concurrent rebuild caller sees ``paused`` already True (its claim
    fails and it exits), so only one rebuild rewrites the counters at a time.
    """
    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(seconds=REBUILD_STALE_S)
    claimed = meta.find_one_and_update(
        {"_id": META_ID,
         "$or": [
             {"paused": {"$ne": True}},
             {"rebuild_started_at": {"$exists": False}},
             {"rebuild_started_at": {"$lt": stale_before}},
         ]},
        {"$set": {"paused": True, "rebuild_owner": owner, "rebuild_started_at": now}},
        upsert=False,
    )
    return claimed is not None


def _release_rebuild(meta, owner: str) -> None:
    """Release the rebuild pause, but only if ``owner`` still holds it."""
    meta.update_one(
        {"_id": META_ID, "rebuild_owner": owner},
        {"$set": {"paused": False}, "$unset": {"rebuild_owner": ""}},
    )


def _normalize_timestamp(ts: datetime) -> datetime | None:
    """Coerce raw timestamps to timezone-aware UTC datetimes."""
    if ts is None:
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def _is_legacy_timestamp(ts: datetime, event_id: ObjectId | None) -> bool:
    """Return True for events whose stored timestamp is a Helsinki wall clock."""
    if event_id is None:
        return False
    try:
        gap_minutes = (ts - event_id.generation_time).total_seconds() / 60.0
    except Exception:
        return False
    return gap_minutes > LEGACY_TIMESTAMP_GAP_MIN


def bucket_keys(ts: datetime | None, event_id: ObjectId | None):
    """Return ``(day, hour, minute)`` in the frame the timestamp was written in.

    Legacy events store the Helsinki wall clock labelled as UTC, so their keys
    are the stored fields themselves; modern events store a real UTC instant and
    need converting to Europe/Helsinki. The rebuild aggregation mirrors this
    rule, so Python and MongoDB always bucket an event identically.
    """
    if ts is None:
        return None
    ts = _normalize_timestamp(ts)
    if ts is None:
        return None
    if _is_legacy_timestamp(ts, event_id):
        ts = ts.astimezone(timezone.utc)
    else:
        ts = ts.astimezone(HELSINKI_TZ)
    return iso_date(ts), two(ts.hour), two(ts.minute)


def _load_markers(aggr, demo_ids) -> dict[ObjectId, ObjectId]:
    """Return the newest raw event id already counted per demo document."""
    markers = {}
    ids = list(demo_ids)
    for start in range(0, len(ids), 1000):
        chunk = ids[start:start + 1000]
        for doc in aggr.find({"_id": {"$in": chunk}}, {"last_event_id": 1}):
            marker = doc.get("last_event_id")
            if marker is not None:
                markers[doc["_id"]] = marker
    return markers


def _rollup_pass(raw, aggr, meta) -> dict:
    """Count every raw event newer than the cursor exactly once."""
    last_seen_id = get_last_seen_id(meta)
    new_events = list(
        raw.find({"_id": {"$gt": last_seen_id}}, {"demo_id": 1, "timestamp": 1})
           .sort("_id", 1)
    )
    if not new_events:
        return {"events": 0, "counted": 0, "skipped": 0}

    on_demand_max_ids = get_on_demand_max_ids(meta)
    markers = _load_markers(aggr, {ev["demo_id"] for ev in new_events})
    counters: dict = {}  # { demo_id: { date: { hour: { minute: count } } } }
    newest: dict[ObjectId, ObjectId] = {}
    skipped = 0

    for ev in new_events:
        demo_id = ev["demo_id"]
        ev_id = ev["_id"]
        if demo_id not in newest or ev_id > newest[demo_id]:
            newest[demo_id] = ev_id

        # Skip events a previous pass (or an on-demand rebuild) already counted
        # so a replayed cursor cannot increment the same event twice.
        marker = markers.get(demo_id)
        if marker is not None and ev_id <= marker:
            skipped += 1
            continue
        max_on_demand_id = on_demand_max_ids.get(str(demo_id))
        if max_on_demand_id is not None and ev_id <= max_on_demand_id:
            skipped += 1
            continue

        keys = bucket_keys(ev.get("timestamp"), ev_id)
        if keys is None:
            continue
        d, h, m = keys

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
            {"$inc": inc_dict, "$max": {"last_event_id": newest[demo_id]}},
            upsert=True
        ))

    if ops:
        aggr.bulk_write(ops, ordered=False)
    # The cursor only advances after the increments landed, and the per-demo
    # marker above keeps a replay of the same range idempotent.
    set_last_seen_id(new_events[-1]["_id"], meta)
    return {"events": len(new_events), "counted": len(new_events) - skipped, "skipped": skipped}


def rollup_events(run_once: bool = False) -> dict | None:
    """
    Process incoming analytics events.

    Only one worker holds the pass at a time; a second worker returns
    immediately with ``{"pass_not_acquired": True}`` instead of racing the
    first one.

    Parameters
    ----------
    run_once : bool
        If True, process currently available events once and return.
        If False (default), run as a continuous poller (existing behaviour).

    Returns
    -------
    dict | None
        Counters of the last pass, ``{"paused": True}`` while a rebuild holds
        the pause, ``{"pass_not_acquired": True}`` when another worker owns the
        pass, or None while running continuously.
    """
    def _single_pass(raw, aggr, meta) -> dict:
        _ensure_meta_doc(meta)
        owner = uuid.uuid4().hex
        if not _claim_pass(meta, owner):
            if _rollup_is_paused(meta):
                LOGGER.info("Analytics rollup is paused (rebuild in progress); skipping pass.")
                return {"paused": True}
            LOGGER.info("Another worker holds the rollup pass; skipping pass.")
            return {"pass_not_acquired": True}
        try:
            return _rollup_pass(raw, aggr, meta)
        finally:
            _release_pass(meta, owner)

    result: dict | None = None

    while True:
        try:
            raw, aggr, meta = _collections()
            result = _single_pass(raw, aggr, meta)
        except Exception:
            # Log instead of dropping the failure silently: an unnoticed error
            # here used to hide gaps and duplicate counts in the counters.
            LOGGER.exception("Analytics rollup pass failed")
            result = {"error": True}

        # If caller requested only a single run, exit now
        if run_once:
            break

        # Wait until next poll interval (existing behaviour)
        sleep_time = POLL_INTERVAL - (time.time() % POLL_INTERVAL)
        with tqdm(total=int(sleep_time), desc="⏳ Waiting for next roll...", bar_format='{l_bar}{bar}| {remaining}s', ncols=70) as pbar:
            for _ in range(int(sleep_time)):
                time.sleep(1)
                pbar.update(1)

    return result


# Server-side mirror of ``bucket_keys``: one collection scan produces the
# finished per-demo minute buckets without shipping raw events to Python.
REBUILD_PIPELINE = [
    {"$project": {
        "demo_id": 1,
        "timestamp": 1,
        "tz": {"$cond": [
            {"$gt": [
                {"$dateDiff": {
                    "startDate": {"$toDate": "$_id"},
                    "endDate": "$timestamp",
                    "unit": "minute",
                }},
                LEGACY_TIMESTAMP_GAP_MIN,
            ]},
            "UTC",
            "Europe/Helsinki",
        ]},
    }},
    {"$group": {
        "_id": {
            "demo": "$demo_id",
            "d": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp", "timezone": "$tz"}},
            "h": {"$dateToString": {"format": "%H", "date": "$timestamp", "timezone": "$tz"}},
            "m": {"$dateToString": {"format": "%M", "date": "$timestamp", "timezone": "$tz"}},
        },
        "n": {"$sum": 1},
        "max_id": {"$max": "$_id"},
    }},
    {"$group": {
        "_id": {"demo": "$_id.demo", "d": "$_id.d", "h": "$_id.h"},
        "mins": {"$push": {"k": "$_id.m", "v": "$n"}},
        "events": {"$sum": "$n"},
        "max_id": {"$max": "$max_id"},
    }},
    {"$addFields": {"min_obj": {"$arrayToObject": "$mins"}}},
    {"$group": {
        "_id": {"demo": "$_id.demo", "d": "$_id.d"},
        "hours": {"$push": {"k": "$_id.h", "v": "$min_obj"}},
        "events": {"$sum": "$events"},
        "max_id": {"$max": "$max_id"},
    }},
    {"$addFields": {"hour_obj": {"$arrayToObject": "$hours"}}},
    {"$group": {
        "_id": "$_id.demo",
        "days": {"$push": {"k": "$_id.d", "v": "$hour_obj"}},
        "events": {"$sum": "$events"},
        "last_event_id": {"$max": "$max_id"},
    }},
    {"$addFields": {"analytics": {"$arrayToObject": "$days"}}},
    {"$project": {"analytics": 1, "events": 1, "last_event_id": 1}},
]


def _wait_for_idle_pass(meta, timeout_s: float) -> bool:
    """Wait until no live rollup pass is running; False when the timeout elapsed."""
    deadline = time.monotonic() + timeout_s
    while _pass_is_live(meta):
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.2)
    return True


def _rebuild_from_raw(raw, aggr) -> dict:
    """Replace every rolled-up document with a recount of the raw events."""
    ops = []
    seen = set()
    events = 0
    replaced = 0

    def _flush():
        if ops:
            aggr.bulk_write(ops, ordered=False)
            ops.clear()

    for doc in raw.aggregate(REBUILD_PIPELINE, allowDiskUse=True):
        demo_id = doc["_id"]
        seen.add(demo_id)
        events += doc.get("events", 0)
        ops.append(UpdateOne(
            {"_id": demo_id},
            {
                "$set": {"analytics": doc.get("analytics") or {}},
                "$max": {"last_event_id": doc.get("last_event_id")},
            },
            upsert=True,
        ))
        replaced += 1
        if len(ops) >= 500:
            _flush()
    _flush()

    stale_ids = [doc["_id"] for doc in aggr.find({}, {"_id": 1}) if doc["_id"] not in seen]
    removed = 0
    for start in range(0, len(stale_ids), 1000):
        result = aggr.delete_many({"_id": {"$in": stale_ids[start:start + 1000]}})
        removed += result.deleted_count

    return {"rebuilt": replaced, "events": events, "removed": removed}


def rebuild_demo_analytics(timeout_s: float = REBUILD_SETTLE_TIMEOUT_S) -> dict:
    """Recount ``d_analytics`` from the raw ``analytics`` events.

    The rebuild claim is acquired atomically, so a second concurrent caller
    (e.g. the scheduled job while an admin runs it manually) is skipped with
    ``{"skipped": True}`` instead of racing. The live rollup is paused first so
    no ``$inc`` can land on top of the rewritten counters, and each rewritten
    document records the newest raw event id it counted so later rollup passes
    skip that range instead of counting it again. If a rollup pass is still
    running when ``timeout_s`` elapses, the rebuild aborts before touching any
    counter (``{"aborted": True, "reason": ...}``) and releases its own claim.
    """
    raw, aggr, meta = _collections()
    _ensure_meta_doc(meta)
    owner = uuid.uuid4().hex
    if not _acquire_rebuild(meta, owner):
        LOGGER.warning("Rebuild skipped: another rebuild is already running.")
        return {"skipped": True}

    try:
        if not _wait_for_idle_pass(meta, timeout_s):
            LOGGER.warning(
                "Rebuild aborted: a rollup pass was still running after %.0fs.",
                timeout_s,
            )
            return {"aborted": True, "reason": "rollup_pass_still_running"}
        stats = _rebuild_from_raw(raw, aggr)
    finally:
        _release_rebuild(meta, owner)

    LOGGER.info("Rebuilt %s", stats)
    return stats


if __name__ == "__main__":
    rollup_events()
