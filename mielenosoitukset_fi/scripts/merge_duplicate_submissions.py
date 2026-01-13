from __future__ import annotations

from datetime import datetime
from typing import Iterable, List, Sequence

from bson import ObjectId

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.demonstrations.audit import log_demo_audit_entry
from mielenosoitukset_fi.utils.classes.Demonstration import Demonstration
from mielenosoitukset_fi.utils.logger import logger

DUPLICATE_GROUP_FIELDS = {
    "title": "$title",
    "organizers": "$organizers",
    "date": "$date",
    "start_time": "$start_time",
    "end_time": "$end_time",
    "address": "$address",
    "city": "$city",
}

REFERENCE_UPDATES = (
    ("submitters", "demonstration_id"),
    ("demo_notifications_queue", "demo_id"),
    ("cases", "demo_id"),
    ("demo_reminders", "demonstration_id"),
)


def _find_duplicate_groups(db, max_groups: int) -> List[Sequence[ObjectId]]:
    pipeline = [
        {
            "$match": {
                "hide": {"$ne": True},
                "merged_into": {"$exists": False},
            }
        },
        {
            "$group": {
                "_id": DUPLICATE_GROUP_FIELDS,
                "ids": {"$push": "$_id"},
                "count": {"$sum": 1},
            }
        },
        {"$match": {"count": {"$gt": 1}}},
        {"$limit": max_groups},
    ]
    return [group["ids"] for group in db.demonstrations.aggregate(pipeline)]


def _sort_key(demo: dict) -> datetime:
    created = demo.get("created_datetime") or demo.get("created_at")
    if isinstance(created, datetime):
        return created
    demo_id = demo.get("_id")
    if isinstance(demo_id, ObjectId):
        return demo_id.generation_time
    return datetime.utcnow()


def _pick_primary_demo(demos: Iterable[dict], submitter_demo_ids: set[ObjectId]) -> dict:
    demos = list(demos)
    candidates = [demo for demo in demos if demo.get("_id") in submitter_demo_ids]
    if not candidates:
        candidates = demos
    return sorted(candidates, key=_sort_key)[0]


def _move_references(db, from_id: ObjectId, to_id: ObjectId) -> None:
    if from_id == to_id:
        return
    for collection, field in REFERENCE_UPDATES:
        db[collection].update_many({field: from_id}, {"$set": {field: to_id}})


def _log_merge_audit(primary_id: ObjectId, merged_id: ObjectId) -> None:
    details = {"kept_demo_id": str(primary_id), "merged_demo_id": str(merged_id)}
    log_demo_audit_entry(
        primary_id,
        "merge_duplicate_submission",
        message="Merged duplicate submission demo",
        details=details,
    )
    log_demo_audit_entry(
        merged_id,
        "merged_into_duplicate_submission",
        message="Duplicate submission demo merged into primary",
        details=details,
    )


def merge_duplicate_submissions(db=None, max_groups: int = 50) -> int:
    if db is None:
        db = DatabaseManager().get_instance().get_db()

    groups = _find_duplicate_groups(db, max_groups=max_groups)
    merged_count = 0

    for ids in groups:
        demos = list(db.demonstrations.find({"_id": {"$in": list(ids)}}))
        demos = [demo for demo in demos if not demo.get("hide") and not demo.get("merged_into")]
        if len(demos) < 2:
            continue

        submitter_demo_ids = {
            doc.get("demonstration_id")
            for doc in db.submitters.find({"demonstration_id": {"$in": list(ids)}}, {"demonstration_id": 1})
            if doc.get("demonstration_id")
        }

        primary_demo = _pick_primary_demo(demos, submitter_demo_ids)
        base_demo = Demonstration.from_dict(primary_demo)

        for demo in demos:
            demo_id = demo.get("_id")
            if demo_id == primary_demo.get("_id"):
                continue
            _move_references(db, demo_id, primary_demo.get("_id"))
            try:
                base_demo.merge(demo_id)
                _log_merge_audit(primary_demo.get("_id"), demo_id)
                merged_count += 1
            except Exception:
                logger.exception("Failed to merge duplicate demo %s into %s", demo_id, primary_demo.get("_id"))

    if merged_count:
        logger.info("Merged %s duplicate submission demos.", merged_count)

    return merged_count


def run(max_groups: int = 50) -> int:
    return merge_duplicate_submissions(max_groups=max_groups)


if __name__ == "__main__":
    run()
