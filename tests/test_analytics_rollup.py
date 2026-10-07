import itertools
import os
import struct
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Any, List

import pytest
from bson import ObjectId

from mielenosoitukset_fi.utils.aggregate_analytics import (
    META_ID,
    rollup_events,
    rebuild_demo_analytics,
    get_last_seen_id,
    set_last_seen_id,
    _claim_pass,
    _release_pass,
    _ensure_meta_doc,
    _pass_is_live,
    _acquire_rebuild,
    _release_rebuild,
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


def _insert_raw_events(db, demo_id, count):
    now = datetime(2026, 6, 1, 9, 50, 0, tzinfo=timezone.utc)
    db.analytics.insert_many(
        {"_id": _oid_at(now), "demo_id": demo_id, "timestamp": now}
        for _ in range(count)
    )
    return now


@pytest.mark.integration
@pytest.mark.jobs
def test_prep_writes_in_place_and_is_idempotent(db):
    from mielenosoitukset_fi.utils.analytics import prep

    demo_id = ObjectId()
    _insert_raw_events(db, demo_id, 2)
    db.prepped_analytics.drop()

    prep()
    prep()  # Second run must not duplicate the rows.

    docs = list(db.prepped_analytics.find({"demo_id": demo_id}))
    assert len(docs) == 1
    assert docs[0]["_id"] == demo_id
    assert docs[0]["views"] == 2


@pytest.mark.integration
@pytest.mark.jobs
def test_prep_updates_changed_counts_without_duplicating(db):
    from mielenosoitukset_fi.utils.analytics import prep

    demo_id = ObjectId()
    _insert_raw_events(db, demo_id, 1)
    db.prepped_analytics.drop()

    prep()
    _insert_raw_events(db, demo_id, 2)  # three raw events in total now
    prep()

    docs = list(db.prepped_analytics.find({"demo_id": demo_id}))
    assert len(docs) == 1
    assert docs[0]["views"] == 3


@pytest.mark.integration
@pytest.mark.jobs
def test_prep_updates_legacy_random_id_rows_in_place(db):
    from mielenosoitukset_fi.utils.analytics import prep

    demo_id = ObjectId()
    _insert_raw_events(db, demo_id, 2)
    db.prepped_analytics.drop()
    legacy_id = ObjectId()  # random _id, as the old drop+reinsert wrote
    db.prepped_analytics.insert_one(
        {"_id": legacy_id, "demo_id": demo_id, "views": 0}
    )

    prep()

    docs = list(db.prepped_analytics.find({"demo_id": demo_id}))
    assert len(docs) == 1
    assert docs[0]["views"] == 2


@pytest.mark.integration
@pytest.mark.jobs
def test_prep_removes_rows_for_demos_without_raw_events(db):
    from mielenosoitukset_fi.utils.analytics import prep

    demo_id = ObjectId()
    _insert_raw_events(db, demo_id, 1)
    stale_demo_id = ObjectId()
    db.prepped_analytics.drop()
    db.prepped_analytics.insert_one(
        {"_id": stale_demo_id, "demo_id": stale_demo_id, "views": 9}
    )

    prep()

    assert db.prepped_analytics.find_one({"_id": stale_demo_id}) is None
    assert db.prepped_analytics.find_one({"_id": demo_id})["views"] == 1


# ── Coordination: atomic pass/rebuild claims ──────────────────────────────
# These tests reset the _meta document so the earlier rollup/replay tests can
# not leave any claim or pause state behind, and the assertions are driven by
# MongoDB documents rather than timers.


def _reset_meta(db):
    db["_meta"].delete_many({"_id": META_ID})
    _ensure_meta_doc(db["_meta"])


@pytest.mark.integration
@pytest.mark.jobs
def test_two_rebuilds_cannot_run_concurrently(db):
    _reset_meta(db)
    meta = db["_meta"]

    assert _acquire_rebuild(meta, "rebuild-a") is True
    assert _acquire_rebuild(meta, "rebuild-b") is False

    doc = meta.find_one({"_id": META_ID})
    assert doc["paused"] is True
    assert doc["rebuild_owner"] == "rebuild-a"

    _release_rebuild(meta, "rebuild-b")  # wrong owner must not clear the pause
    doc = meta.find_one({"_id": META_ID})
    assert doc["paused"] is True
    assert doc["rebuild_owner"] == "rebuild-a"

    _release_rebuild(meta, "rebuild-a")
    doc = meta.find_one({"_id": META_ID})
    assert doc["paused"] is False
    assert "rebuild_owner" not in doc

    assert _acquire_rebuild(meta, "rebuild-c") is True


@pytest.mark.integration
@pytest.mark.jobs
def test_public_rebuild_is_skipped_while_another_rebuild_holds(db):
    _reset_meta(db)
    meta = db["_meta"]

    assert _acquire_rebuild(meta, "rebuild-holder") is True
    stats = rebuild_demo_analytics(timeout_s=0)

    assert stats == {"skipped": True}
    doc = meta.find_one({"_id": META_ID})
    assert doc["paused"] is True  # the holder's claim is untouched
    assert doc["rebuild_owner"] == "rebuild-holder"

    _release_rebuild(meta, "rebuild-holder")
    doc = meta.find_one({"_id": META_ID})
    assert doc["paused"] is False


@pytest.mark.integration
@pytest.mark.jobs
def test_two_workers_cannot_claim_the_same_pass(db):
    _reset_meta(db)
    meta = db["_meta"]

    assert _claim_pass(meta, "worker-a") is True
    assert _claim_pass(meta, "worker-b") is False

    doc = meta.find_one({"_id": META_ID})
    assert doc["pass_in_progress"] is True
    assert doc["pass_owner"] == "worker-a"

    _release_pass(meta, "worker-a")
    doc = meta.find_one({"_id": META_ID})
    assert doc["pass_in_progress"] is False

    assert _claim_pass(meta, "worker-c") is True


@pytest.mark.integration
@pytest.mark.jobs
def test_failed_pass_claim_stops_without_overwriting_pass_state(db):
    _reset_meta(db)
    meta = db["_meta"]

    demo_id = ObjectId()
    now = datetime(2026, 6, 1, 9, 50, 0, tzinfo=timezone.utc)
    db.analytics.insert_one({"_id": _oid_at(now), "demo_id": demo_id, "timestamp": now})
    _claim_pass(meta, "worker-holder")

    before = meta.find_one({"_id": META_ID})

    stats = rollup_events(run_once=True)

    assert stats == {"pass_not_acquired": True}
    assert db.d_analytics.find_one({"_id": demo_id}) is None  # no counting happened
    after = meta.find_one({"_id": META_ID})
    assert after["pass_in_progress"] is True
    assert after["pass_owner"] == "worker-holder"
    assert after["pass_started_at"] == before["pass_started_at"]

    _release_pass(meta, "worker-holder")


@pytest.mark.integration
@pytest.mark.jobs
def test_rebuild_aborts_when_rollup_pass_does_not_settle(db):
    _reset_meta(db)
    meta = db["_meta"]

    demo_id = ObjectId()
    now = datetime(2026, 6, 1, 9, 50, 0, tzinfo=timezone.utc)
    for _ in range(3):
        db.analytics.insert_one({"_id": _oid_at(now), "demo_id": demo_id, "timestamp": now})
    db.d_analytics.insert_one(
        {"_id": demo_id, "analytics": {"2026-06-01": {"12": {"50": 8}}}}
    )

    # A live pass whose worker never finishes.
    _claim_pass(meta, "worker-holder")
    assert _pass_is_live(meta) is True

    stats = rebuild_demo_analytics(timeout_s=0)

    assert stats == {"aborted": True, "reason": "rollup_pass_still_running"}
    # The counters were not rewritten before the timeout.
    doc = db.d_analytics.find_one({"_id": demo_id})
    assert doc["analytics"]["2026-06-01"]["12"]["50"] == 8
    assert "last_event_id" not in doc

    meta_doc = meta.find_one({"_id": META_ID})
    assert meta_doc["paused"] is False          # its own claim was released
    assert "rebuild_owner" not in meta_doc
    assert meta_doc["pass_in_progress"] is True  # the pass holder is untouched
    assert meta_doc["pass_owner"] == "worker-holder"

    _release_pass(meta, "worker-holder")


@pytest.mark.integration
@pytest.mark.jobs
def test_stale_pass_claim_can_be_taken_over(db):
    _reset_meta(db)
    meta = db["_meta"]

    # A crashed worker left the flag set long ago with no newer heartbeat.
    now = datetime.now(timezone.utc)
    meta.update_one(
        {"_id": META_ID},
        {"$set": {
            "pass_in_progress": True,
            "pass_owner": "crashed-worker",
            "pass_started_at": now - timedelta(hours=2),
        }},
    )
    assert _pass_is_live(meta) is False

    assert _claim_pass(meta, "new-worker") is True
    doc = meta.find_one({"_id": META_ID})
    assert doc["pass_owner"] == "new-worker"
    # pymongo reads the stored UTC instant back without a tzinfo; tag it as UTC
    # so the comparison stays aware.
    assert doc["pass_started_at"].replace(tzinfo=timezone.utc) > now - timedelta(minutes=1)

    _release_pass(meta, "new-worker")

    # The same take-over applies to an abandoned rebuild pause.
    meta.update_one(
        {"_id": META_ID},
        {"$set": {
            "paused": True,
            "rebuild_owner": "crashed-rebuild",
            "rebuild_started_at": now - timedelta(hours=2),
        }},
    )
    assert _acquire_rebuild(meta, "new-rebuild") is True
    doc = meta.find_one({"_id": META_ID})
    assert doc["paused"] is True
    assert doc["rebuild_owner"] == "new-rebuild"
    _release_rebuild(meta, "new-rebuild")


@pytest.mark.integration
@pytest.mark.jobs
def test_flag_without_timestamp_is_not_a_live_pass(db):
    _reset_meta(db)
    meta = db["_meta"]

    # Flags written by a pre-coordination deploy have no pass_started_at; they
    # must never block a rebuild (the very first rebuild releases them).
    meta.update_one({"_id": META_ID}, {"$set": {"pass_in_progress": True}})
    assert _pass_is_live(meta) is False
    assert _claim_pass(meta, "worker-a") is True
    _release_pass(meta, "worker-a")