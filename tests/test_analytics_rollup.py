import itertools
import os
import struct
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any, List

import pytest
from bson import ObjectId

from mielenosoitukset_fi.utils.aggregate_analytics import (
    rollup_events,
    rebuild_demo_analytics,
    get_last_seen_id,
    set_last_seen_id,
)

# Monotonic per-process bytes so crafted ObjectIds keep byte order = counter
# order even when several share the same creation-time second.
_MACHINE_BYTES = os.urandom(5)
_MACHINE_COUNTER = itertools.count(1)


def _oid_at(dt) -> ObjectId:
    """Build a unique ObjectId whose creation time is ``dt`` (UTC)."""
    ts = int(dt.replace(tzinfo=timezone.utc).timestamp())
    raw = struct.pack(">I", ts) + _MACHINE_BYTES + struct.pack(">I", next(_MACHINE_COUNTER))[-3:]
    return ObjectId(raw)


def _total_views(analytics) -> int:
    return sum(
        minute_count
        for days in analytics.values()
        for hours in days.values()
        for minute_count in hours.values()
    )


@pytest.mark.integration
@pytest.mark.jobs
def test_rollup_buckets_legacy_and_modern_timestamps_into_same_counts(db):
    demo_id = ObjectId()
    legacy_oid = _oid_at(datetime(2026, 6, 1, 9, 50, 0, tzinfo=timezone.utc))
    modern_oid = _oid_at(datetime(2026, 6, 1, 9, 50, 0, tzinfo=timezone.utc))

    # Legacy shape: ObjectId at the real instant (09:50Z) but the stored
    # timestamp is the Helsinki wall clock (12:50) persisted as UTC.
    db.analytics.insert_one({"demo_id": demo_id, "timestamp": datetime(2026, 6, 1, 12, 50), "_id": legacy_oid})
    # Modern shape: ObjectId and timestamp both at the real instant (09:50Z).
    db.analytics.insert_one({"demo_id": demo_id, "timestamp": datetime(2026, 6, 1, 9, 50, tzinfo=timezone.utc), "_id": modern_oid})

    stats = rollup_events(run_once=True)

    assert stats == {"events": 2, "counted": 2, "skipped": 0}
    doc = db.d_analytics.find_one({"_id": demo_id})
    assert doc["analytics"]["2026-06-01"]["12"]["50"] == 2
    assert doc["last_event_id"] == modern_oid


@pytest.mark.integration
@pytest.mark.jobs
def test_rebuild_repairs_inflated_counters_and_prunes_stale_docs(db):
    demo_id = ObjectId()
    stale_demo_id = ObjectId()
    now = datetime(2026, 6, 1, 9, 50, 0, tzinfo=timezone.utc)
    event_ids = [_oid_at(now), _oid_at(now), _oid_at(now)]
    for oid in event_ids:
        db.analytics.insert_one({"_id": oid, "demo_id": demo_id, "timestamp": now})

    # Pre-existing rolled-up doc with doubly-counted (inflated) values plus a
    # stale doc whose demo has no raw events at all.
    db.d_analytics.insert_one({"_id": demo_id, "analytics": {"2026-06-01": {"12": {"50": 8}}}})
    db.d_analytics.insert_one({"_id": stale_demo_id, "analytics": {"2026-06-01": {"12": {"50": 2}}}})

    stats = rebuild_demo_analytics(timeout_s=0)

    assert stats["removed"] == 1
    doc = db.d_analytics.find_one({"_id": demo_id})
    assert _total_views(doc["analytics"]) == 3
    assert doc["analytics"]["2026-06-01"]["12"]["50"] == 3
    assert doc["last_event_id"] == max(event_ids)

    meta = db["_meta"].find_one({"_id": "analytics_rollup"})
    assert meta.get("paused") is False
    assert db.d_analytics.find_one({"_id": stale_demo_id}) is None


@pytest.mark.integration
@pytest.mark.jobs
def test_rollup_replay_does_not_double_count(db):
    demo_id = ObjectId()
    now = datetime(2026, 6, 1, 9, 50, 0, tzinfo=timezone.utc)
    ev1 = _oid_at(now)
    ev2 = _oid_at(now)
    db.analytics.insert_one({"_id": ev1, "demo_id": demo_id, "timestamp": now})
    db.analytics.insert_one({"_id": ev2, "demo_id": demo_id, "timestamp": now})

    # Simulate a replay: the cursor is reset to the beginning of time. Events
    # for demos that were already rolled up (in this or earlier tests) have a
    # last_event_id marker and must be skipped rather than counted again.
    set_last_seen_id(ObjectId("000000000000000000000000"), db["_meta"])
    stats = rollup_events(run_once=True)

    doc = db.d_analytics.find_one({"_id": demo_id})
    assert _total_views(doc["analytics"]) == 2
    assert doc["last_event_id"] == max(ev1, ev2)
    assert stats["counted"] == stats["events"] - stats["skipped"]

    # Replaying again must not change the already-counted demo.
    set_last_seen_id(ObjectId("000000000000000000000000"), db["_meta"])
    rollup_events(run_once=True)
    doc = db.d_analytics.find_one({"_id": demo_id})
    assert _total_views(doc["analytics"]) == 2

    # New events are still counted on top of the marker.
    ev3 = _oid_at(now)
    db.analytics.insert_one({"_id": ev3, "demo_id": demo_id, "timestamp": now})
    rollup_events(run_once=True)
    doc = db.d_analytics.find_one({"_id": demo_id})
    assert _total_views(doc["analytics"]) == 3
    assert doc["last_event_id"] == ev3


@pytest.mark.integration
@pytest.mark.jobs
def test_rollup_skips_pass_while_rebuild_paused(db):
    demo_id = ObjectId()
    now = datetime(2026, 6, 1, 9, 50, 0, tzinfo=timezone.utc)
    db.analytics.insert_one({"_id": _oid_at(now), "demo_id": demo_id, "timestamp": now})
    db["_meta"].update_one({"_id": "analytics_rollup"}, {"$set": {"paused": True}}, upsert=True)

    stats = rollup_events(run_once=True)

    assert stats == {"paused": True}
    assert db.d_analytics.find_one({"_id": demo_id}) is None


@pytest.mark.integration
@pytest.mark.jobs
def test_rebuild_job_is_registered(app, db):
    job_manager = app.extensions["job_manager"]
    job_manager._ensure_job_documents()

    job_keys = {job["key"] for job in job_manager.list_jobs()}
    assert "rebuild_d_analytics" in job_keys
    job_doc = db.background_jobs.find_one({"_id": "rebuild_d_analytics"})
    assert job_doc is not None
    assert job_doc["allow_manual_trigger"] is True