"""Durable, single-document receipt for content rollback history delivery.

MongoDB's update pipeline captures the actual pre-image and its content change
alongside the change itself; a separate idempotent projection may then retry.
Only one pending receipt is allowed per demonstration. This is not a
cross-document transaction or a replacement for the general audit system.
"""

from bson import ObjectId
from pymongo import ReturnDocument

from mielenosoitukset_fi.utils.logger import logger


PENDING_ROLLBACK_HISTORY = "_pending_rollback_history"


def restore_merge_conflict(db, primary_before, primary_merged, removed):
    """Compensate this merge's writes without overwriting later concurrent data.

    Insert-only restoration protects recreated secondary IDs. The primary is
    restored only while its complete document still equals this merge's result.
    False means the retained backup still needs operator recovery.
    """
    restored = True
    try:
        for document in removed:
            db.demonstrations.update_one(
                {"_id": document["_id"]}, {"$setOnInsert": document}, upsert=True,
            )
            if db.demonstrations.find_one({"_id": document["_id"]}) != document:
                restored = False
        result = db.demonstrations.replace_one({
            "_id": primary_before["_id"],
            "$expr": {"$eq": ["$$ROOT", {"$literal": primary_merged}]},
        }, primary_before)
        if not result.matched_count and db.demonstrations.find_one({"_id": primary_before["_id"]}) != primary_before:
            restored = False
    except Exception as error:
        logger.warning("Merge recovery pending (%s)", type(error).__name__)
        return False
    return restored


def flush_rollback_history(db, demo_id):
    """Project a committed receipt once, retaining it on either delivery failure."""
    document = db.demonstrations.find_one(
        {"_id": demo_id}, {PENDING_ROLLBACK_HISTORY: 1},
    ) or {}
    receipt = document.get(PENDING_ROLLBACK_HISTORY)
    if receipt is None:
        return True
    if not isinstance(receipt, dict) or not isinstance(receipt.get("_id"), ObjectId):
        return False
    try:
        db.demo_edit_history.update_one(
            {"_id": receipt["_id"]}, {"$setOnInsert": receipt}, upsert=True,
        )
        db.demonstrations.update_one(
            {"_id": demo_id, f"{PENDING_ROLLBACK_HISTORY}._id": receipt["_id"]},
            {"$unset": {PENDING_ROLLBACK_HISTORY: ""}},
        )
    except Exception as error:
        # No receipt content or database exception payload in logs.
        logger.warning("Rollback history delivery pending (%s)", type(error).__name__)
        return False
    return True


def commit_rollback(db, query, changes, metadata):
    """Atomically apply guarded content and retain its exact before/after event.

    Requires MongoDB 4.2+ update pipelines, but not replica-set transactions.
    All caller values are literals, never executable aggregation expressions.
    A pending receipt must be delivered before another rollback is admitted.
    """
    snapshot = {"$arrayToObject": {"$filter": {
        "input": {"$objectToArray": "$$ROOT"}, "as": "field",
        "cond": {"$ne": ["$$field.k", PENDING_ROLLBACK_HISTORY]},
    }}}
    receipt = {key: {"$literal": value} for key, value in metadata.items()}
    receipt.update({
        "_id": {"$literal": ObjectId()},
        "old_demo": snapshot,
        "new_demo": {"$mergeObjects": [snapshot, {"$literal": changes}]},
    })
    return db.demonstrations.find_one_and_update(
        {**query, PENDING_ROLLBACK_HISTORY: {"$exists": False}},
        [
            {"$set": {PENDING_ROLLBACK_HISTORY: receipt}},
            {"$set": {key: {"$literal": value} for key, value in changes.items()}},
        ],
        return_document=ReturnDocument.BEFORE,
    )
