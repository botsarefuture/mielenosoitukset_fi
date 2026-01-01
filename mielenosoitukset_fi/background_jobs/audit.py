from __future__ import annotations

import threading
from copy import deepcopy
from typing import Any, Dict, Iterable, Optional

from bson import ObjectId
from pymongo.collection import Collection
from contextlib import contextmanager

from mielenosoitukset_fi.demonstrations.audit import record_demo_change

_thread_local = threading.local()
_PATCHED = False
_ORIGINALS: Dict[str, Any] = {}


def _set_recorder(recorder):
    _thread_local.recorder = recorder


def _get_recorder():
    return getattr(_thread_local, "recorder", None)


class DemoChangeRecorder:
    """Tracks demo modifications performed by a background job."""

    def __init__(self, job_key: str, run_id: ObjectId):
        self.job_key = job_key
        self.run_id = str(run_id)
        self.actor = {
            "user_id": None,
            "username": f"[JOB] {job_key}",
            "source": "background_job",
        }

    def _build_details(self, operation: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        details = {
            "job_key": self.job_key,
            "job_run_id": self.run_id,
            "operation": operation,
        }
        if extra:
            details.update(extra)
        return details

    def record(self, before: Optional[Dict[str, Any]], after: Optional[Dict[str, Any]], operation: str, extra=None):
        demo_id = (after or before or {}).get("_id")
        if not demo_id:
            return
        record_demo_change(
            demo_id=demo_id,
            old_data=before,
            new_data=after,
            action=f"{self.job_key}:{operation}",
            message=f"{self.job_key} {operation}",
            actor=self.actor,
            extra_details=self._build_details(operation, extra),
        )


def _ensure_patched():
    global _PATCHED
    if _PATCHED:
        return

    def wrap(method_name):
        original = getattr(Collection, method_name)
        _ORIGINALS[method_name] = original

        def wrapper(self, *args, **kwargs):
            recorder = _get_recorder()
            track = recorder and self.name == "demonstrations"
            if method_name in {"update_one", "update_many"} and track:
                return _handle_update(method_name, original, recorder, self, *args, **kwargs)
            if method_name in {"replace_one", "find_one_and_replace"} and track:
                return _handle_replace(method_name, original, recorder, self, *args, **kwargs)
            if method_name in {"find_one_and_update"} and track:
                return _handle_find_one_and_update(method_name, original, recorder, self, *args, **kwargs)
            if method_name in {"insert_one", "insert_many"} and track:
                return _handle_insert(method_name, original, recorder, self, *args, **kwargs)
            if method_name in {"delete_one", "delete_many", "find_one_and_delete"} and track:
                return _handle_delete(method_name, original, recorder, self, *args, **kwargs)
            return original(self, *args, **kwargs)

        setattr(Collection, method_name, wrapper)

    for name in [
        "update_one",
        "update_many",
        "replace_one",
        "find_one_and_replace",
        "find_one_and_update",
        "insert_one",
        "insert_many",
        "delete_one",
        "delete_many",
        "find_one_and_delete",
    ]:
        wrap(name)

    _PATCHED = True


def _materialize_docs(collection: Collection, filter_doc) -> Dict[ObjectId, Dict[str, Any]]:
    docs = {}
    for doc in collection.find(deepcopy(filter_doc)):
        if "_id" in doc:
            docs[doc["_id"]] = doc
    return docs


def _fetch_docs_by_ids(collection: Collection, ids: Iterable[ObjectId]) -> Dict[ObjectId, Dict[str, Any]]:
    if not ids:
        return {}
    cursor = collection.find({"_id": {"$in": list(ids)}})
    return {doc["_id"]: doc for doc in cursor}


def _handle_update(method_name, original, recorder, collection, filter_doc, update_doc, *args, **kwargs):
    before = _materialize_docs(collection, filter_doc)
    result = original(collection, filter_doc, update_doc, *args, **kwargs)
    if not before:
        return result
    after = _fetch_docs_by_ids(collection, before.keys())
    for _id, old_doc in before.items():
        recorder.record(
            old_doc,
            after.get(_id),
            method_name,
            extra={"filter": str(filter_doc), "update": str(update_doc)},
        )
    return result


def _handle_replace(method_name, original, recorder, collection, filter_doc, replacement, *args, **kwargs):
    before = _materialize_docs(collection, filter_doc)
    result = original(collection, filter_doc, replacement, *args, **kwargs)
    if not before:
        return result
    after = _fetch_docs_by_ids(collection, before.keys())
    for _id, old_doc in before.items():
        recorder.record(old_doc, after.get(_id), method_name, extra={"filter": str(filter_doc)})
    return result


def _handle_find_one_and_update(method_name, original, recorder, collection, filter_doc, update_doc, *args, **kwargs):
    before_doc = collection.find_one(deepcopy(filter_doc))
    result = original(collection, filter_doc, update_doc, *args, **kwargs)
    if before_doc and "_id" in before_doc:
        after_doc = collection.find_one({"_id": before_doc["_id"]})
        recorder.record(
            before_doc,
            after_doc,
            method_name,
            extra={"filter": str(filter_doc), "update": str(update_doc)},
        )
    return result


def _handle_insert(method_name, original, recorder, collection, docs, *args, **kwargs):
    if method_name == "insert_one":
        result = original(collection, docs, *args, **kwargs)
        inserted_id = result.inserted_id
        new_doc = collection.find_one({"_id": inserted_id})
        recorder.record(None, new_doc, method_name, extra={"inserted_id": str(inserted_id)})
        return result
    # insert_many
    result = original(collection, docs, *args, **kwargs)
    inserted_ids = result.inserted_ids or []
    new_docs = _fetch_docs_by_ids(collection, inserted_ids)
    for _id, doc in new_docs.items():
        recorder.record(None, doc, method_name, extra={"inserted_id": str(_id)})
    return result


def _handle_delete(method_name, original, recorder, collection, filter_doc, *args, **kwargs):
    before = _materialize_docs(collection, filter_doc)
    result = original(collection, filter_doc, *args, **kwargs)
    for _id, old_doc in before.items():
        recorder.record(old_doc, None, method_name, extra={"filter": str(filter_doc)})
    return result


@contextmanager
def job_audit_context(job_key: str, run_id: ObjectId):
    """Context manager that enables demo auditing within background jobs."""
    _ensure_patched()
    recorder = DemoChangeRecorder(job_key, run_id)
    _set_recorder(recorder)
    try:
        yield
    finally:
        _set_recorder(None)
