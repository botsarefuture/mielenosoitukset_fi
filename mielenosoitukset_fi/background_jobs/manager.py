from __future__ import annotations

import atexit
import os
import socket
import threading
import traceback
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from pymongo import ReturnDocument

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.logger import logger

from .definitions import JOB_DEFINITION_MAP, JOB_DEFINITIONS, JobDefinition
from .audit import job_audit_context


class BackgroundJobLeadership:
    """Coordinates which worker process owns the scheduler."""

    def __init__(
        self,
        manager: BackgroundJobManager,
        key: str,
        ttl_seconds: int = 120,
        refresh_seconds: Optional[int] = None,
    ):
        self.manager = manager
        self._collection = DatabaseManager().get_instance().get_db()["background_job_leader"]
        self.key = key
        self.ttl_seconds = max(30, ttl_seconds)
        self.refresh_seconds = refresh_seconds or max(5, self.ttl_seconds // 3)
        self.owner_id = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex}"
        self.is_leader = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._started = False

    def start(self):
        if self._started:
            return
        self._started = True
        if self._claim():
            self._on_acquired()
        else:
            logger.info(
                "Worker %s waiting for background job leadership (key=%s).",
                self.owner_id,
                self.key,
            )
        self._thread = threading.Thread(target=self._run, name="bg-job-leadership", daemon=True)
        self._thread.start()
        atexit.register(self.stop)

    def stop(self):
        self._stop_event.set()
        if self.is_leader:
            self._on_lost()
        self._release()

    def _run(self):
        while not self._stop_event.wait(self.refresh_seconds):
            has_lock = self._claim()
            if has_lock and not self.is_leader:
                self._on_acquired()
            elif not has_lock and self.is_leader:
                self._on_lost()
        self._release()

    def _claim(self) -> bool:
        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=self.ttl_seconds)
        try:
            doc = self._collection.find_one_and_update(
                {
                    "_id": self.key,
                    "$or": [
                        {"owner_id": self.owner_id},
                        {"expires_at": {"$lte": now}},
                        {"expires_at": {"$exists": False}},
                    ],
                },
                {
                    "$set": {
                        "owner_id": self.owner_id,
                        "owner_host": socket.gethostname(),
                        "owner_pid": os.getpid(),
                        "refreshed_at": now,
                        "expires_at": expires_at,
                    }
                },
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
        except Exception:
            logger.exception("Failed to negotiate background job leadership.")
            return False
        return doc.get("owner_id") == self.owner_id

    def _release(self):
        try:
            self._collection.delete_one({"_id": self.key, "owner_id": self.owner_id})
        except Exception:
            pass

    def _on_acquired(self):
        logger.info("Worker %s became background job leader for %s.", self.owner_id, self.key)
        self.is_leader = True
        self.manager.start()

    def _on_lost(self):
        logger.warning("Worker %s lost background job leadership for %s.", self.owner_id, self.key)
        self.is_leader = False
        self.manager.shutdown()


class BackgroundJobManager:
    """Wraps APScheduler and stores job history in MongoDB."""

    def __init__(self, app=None, scheduler: Optional[BackgroundScheduler] = None):
        self.app = app
        self.scheduler = scheduler or BackgroundScheduler()
        self._db = DatabaseManager().get_instance().get_db()
        self._ensure_job_documents()

    def attach_app(self, app):
        self.app = app

    # ------------------------------------------------------------------ #
    # Scheduler lifecycle
    # ------------------------------------------------------------------ #
    def start(self):
        if not self.app:
            raise RuntimeError("BackgroundJobManager requires an app context before start.")

        self.reload_all()
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Background job scheduler started with %s jobs.", len(self.scheduler.get_jobs()))

    def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def reload_all(self):
        for job in JOB_DEFINITIONS:
            self.reload_job(job.key)

    def reload_job(self, job_key: str):
        job_def = self._require_job(job_key)
        doc = self._get_job_document(job_key)
        if not doc.get("enabled", True):
            self._remove_job(job_key)
            return None

        trigger = doc.get("trigger", "interval")
        trigger_args = doc.get("trigger_args") or {}
        scheduler_job = self.scheduler.add_job(
            func=lambda jk=job_key: self._execute_job(jk),
            trigger=trigger,
            id=job_key,
            replace_existing=True,
            **trigger_args,
        )
        self._update_next_run(job_key, self._get_next_run_time(scheduler_job))
        logger.info("Scheduled job %s (%s)", job_key, job_def.name)
        return scheduler_job

    def _remove_job(self, job_key: str):
        try:
            self.scheduler.remove_job(job_key)
            logger.info("Removed job %s from scheduler because it is disabled.", job_key)
        except Exception:
            pass
        self._db.background_jobs.update_one(
            {"_id": job_key},
            {"$unset": {"next_run_at": ""}},
        )

    # ------------------------------------------------------------------ #
    # Administrative helpers
    # ------------------------------------------------------------------ #
    def list_jobs(self) -> List[Dict[str, Any]]:
        docs = {doc["_id"]: doc for doc in self._db.background_jobs.find({})}
        items: List[Dict[str, Any]] = []
        for definition in JOB_DEFINITIONS:
            doc = docs.get(definition.key, {})
            scheduler_job = self.scheduler.get_job(definition.key)
            items.append(
                {
                    "key": definition.key,
                    "name": definition.name,
                    "description": definition.description,
                    "trigger": doc.get("trigger", "interval"),
                    "trigger_args": doc.get("trigger_args", {}),
                    "enabled": doc.get("enabled", True),
                    "allow_manual_trigger": doc.get("allow_manual_trigger", True),
                    "allow_interval_override": doc.get("allow_interval_override", True),
                    "last_run_status": doc.get("last_run_status"),
                    "last_run_started_at": doc.get("last_run_started_at"),
                    "last_run_finished_at": doc.get("last_run_finished_at"),
                    "last_run_triggered_by": doc.get("last_run_triggered_by"),
                    "last_duration_seconds": doc.get("last_duration_seconds"),
                    "last_message": doc.get("last_message"),
                    "next_run_at": (scheduler_job.next_run_time if scheduler_job else doc.get("next_run_at")),
                }
            )
        return items

    def get_job(self, job_key: str) -> Dict[str, Any]:
        return self._get_job_document(job_key)

    def get_job_info(self, job_key: str) -> Dict[str, Any]:
        doc = self._get_job_document(job_key)
        definition = self._require_job(job_key)
        scheduler_job = self.scheduler.get_job(job_key)
        return {
            "key": definition.key,
            "name": definition.name,
            "description": definition.description,
            "trigger": doc.get("trigger", "interval"),
            "trigger_args": doc.get("trigger_args", {}),
            "enabled": doc.get("enabled", True),
            "allow_manual_trigger": doc.get("allow_manual_trigger", True),
            "allow_interval_override": doc.get("allow_interval_override", True),
            "last_run_status": doc.get("last_run_status"),
            "last_run_started_at": doc.get("last_run_started_at"),
            "last_run_finished_at": doc.get("last_run_finished_at"),
            "last_run_triggered_by": doc.get("last_run_triggered_by"),
            "last_duration_seconds": doc.get("last_duration_seconds"),
            "last_message": doc.get("last_message"),
            "next_run_at": self._get_next_run_time(scheduler_job) if scheduler_job else doc.get("next_run_at"),
        }

    def get_recent_runs(self, job_key: Optional[str] = None, limit: int = 50, skip: int = 0) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {}
        if job_key:
            query["job_key"] = job_key

        cursor = (
            self._db.background_job_runs.find(query)
            .sort("started_at", -1)
            .skip(max(0, skip))
            .limit(limit)
        )
        runs: List[Dict[str, Any]] = []
        for doc in cursor:
            runs.append(self._serialize_run(doc))
        return runs

    def count_runs(self, job_key: Optional[str] = None) -> int:
        query: Dict[str, Any] = {}
        if job_key:
            query["job_key"] = job_key
        return self._db.background_job_runs.count_documents(query)

    def set_job_enabled(self, job_key: str, enabled: bool):
        self._require_job(job_key)
        self._db.background_jobs.update_one(
            {"_id": job_key},
            {"$set": {"enabled": enabled, "updated_at": datetime.utcnow()}},
        )
        if enabled:
            self.reload_job(job_key)
        else:
            self._remove_job(job_key)

    def update_interval(self, job_key: str, value: int, unit: str):
        job_def = self._require_job(job_key)
        if not self._get_job_document(job_key).get("allow_interval_override", True):
            raise ValueError(f"Job {job_def.name} does not allow interval overrides.")

        safe_unit = unit if unit in {"minutes", "hours", "days"} else None
        if not safe_unit:
            raise ValueError("Unsupported interval unit.")

        interval_value = max(1, int(value))

        trigger_args = {safe_unit: interval_value}
        updated = self._db.background_jobs.find_one_and_update(
            {"_id": job_key},
            {
                "$set": {
                    "trigger": "interval",
                    "trigger_args": trigger_args,
                    "updated_at": datetime.utcnow(),
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        self.reload_job(job_key)
        return updated

    def run_job_now(self, job_key: str, triggered_by: str, metadata: Optional[Dict[str, Any]] = None):
        self._require_job(job_key)
        thread = threading.Thread(
            target=self._execute_job,
            kwargs={"job_key": job_key, "triggered_by": triggered_by, "metadata": metadata or {}},
            daemon=True,
        )
        thread.start()
        return thread

    # ------------------------------------------------------------------ #
    # Execution + logging
    # ------------------------------------------------------------------ #
    def _execute_job(self, job_key: str, triggered_by: str = "scheduler", metadata: Optional[Dict[str, Any]] = None):
        job_def = self._require_job(job_key)
        now = datetime.utcnow()
        run_doc = {
            "job_key": job_key,
            "job_name": job_def.name,
            "triggered_by": triggered_by,
            "metadata": metadata or {},
            "started_at": now,
            "status": "running",
        }
        run_id = self._db.background_job_runs.insert_one(run_doc).inserted_id
        status = "success"
        message = "Completed successfully."
        tb_text = None
        try:
            if self.app:
                with self.app.app_context():
                    with job_audit_context(job_key, run_id):
                        job_def.func()
            else:
                with job_audit_context(job_key, run_id):
                    job_def.func()
        except Exception as exc:  # pragma: no cover - defensive logging
            status = "error"
            message = str(exc)
            tb_text = traceback.format_exc()
            logger.exception("Background job %s failed.", job_key)
        finally:
            finished_at = datetime.utcnow()
            duration_seconds = (finished_at - now).total_seconds()
            update_fields: Dict[str, Any] = {
                "finished_at": finished_at,
                "status": status,
                "message": message,
                "duration_seconds": duration_seconds,
            }
            if tb_text:
                update_fields["trace"] = tb_text
            self._db.background_job_runs.update_one({"_id": run_id}, {"$set": update_fields})

            self._db.background_jobs.update_one(
                {"_id": job_key},
                {
                    "$set": {
                        "last_run_status": status,
                        "last_run_started_at": now,
                        "last_run_finished_at": finished_at,
                        "last_duration_seconds": duration_seconds,
                        "last_message": message,
                        "last_run_triggered_by": triggered_by,
                        "updated_at": finished_at,
                    }
                },
            )

            scheduler_job = self.scheduler.get_job(job_key)
            if scheduler_job:
                self._update_next_run(job_key, self._get_next_run_time(scheduler_job))

    def _update_next_run(self, job_key: str, next_run_time):
        if not next_run_time:
            update = {"$unset": {"next_run_at": ""}}
        else:
            update = {"$set": {"next_run_at": next_run_time}}
        self._db.background_jobs.update_one({"_id": job_key}, update)
    
    @staticmethod
    def _get_next_run_time(job):
        if not job:
            return None
        next_run = getattr(job, "next_run_time", None)
        if callable(next_run):
            try:
                next_run = next_run()
            except TypeError:
                try:
                    next_run = next_run(None)
                except Exception:
                    next_run = None
        if not next_run and hasattr(job, "trigger"):
            try:
                next_run = job.trigger.get_next_fire_time(None, datetime.utcnow())
            except Exception:
                next_run = None
        return next_run

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _ensure_job_documents(self):
        for definition in JOB_DEFINITIONS:
            # Avoid duplicate field paths in $setOnInsert/$set by splitting immutable vs updateable
            self._db.background_jobs.update_one(
                {"_id": definition.key},
                {
                    "$setOnInsert": {
                        "_id": definition.key,
                        "trigger": definition.default_trigger.get("trigger", "interval"),
                        "trigger_args": definition.default_trigger.get("trigger_args", {}),
                        "enabled": True,
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    },
                    "$set": {
                        "name": definition.name,
                        "description": definition.description,
                        "allow_manual_trigger": definition.allow_manual_trigger,
                        "allow_interval_override": definition.allow_interval_override,
                    },
                },
                upsert=True,
            )

    def _get_job_document(self, job_key: str) -> Dict[str, Any]:
        doc = self._db.background_jobs.find_one({"_id": job_key})
        if not doc:
            self._ensure_job_documents()
            doc = self._db.background_jobs.find_one({"_id": job_key})
        if not doc:
            raise KeyError(f"No job definition found for key {job_key}")
        return doc

    @staticmethod
    def _serialize_run(doc: Dict[str, Any]) -> Dict[str, Any]:
        run = dict(doc)
        run["id"] = str(run.pop("_id"))
        return run

    @staticmethod
    def _require_job(job_key: str) -> JobDefinition:
        job_def = JOB_DEFINITION_MAP.get(job_key)
        if not job_def:
            raise KeyError(f"Unknown job '{job_key}'")
        return job_def


def init_background_jobs(app):
    """Factory called from the Flask app factory."""
    manager = BackgroundJobManager(app=app)
    app.extensions["job_manager"] = manager
    if app.config.get("DISABLE_BACKGROUND_JOBS"):
        logger.warning("Background jobs disabled via config flag.")
        return manager

    leader_key = app.config.get("BACKGROUND_JOB_LEADER_KEY", "default_background_jobs")
    ttl_seconds = int(app.config.get("BACKGROUND_JOB_LEADER_TTL_SECONDS", 120))
    refresh_seconds = app.config.get("BACKGROUND_JOB_LEADER_REFRESH_SECONDS")
    leadership = BackgroundJobLeadership(
        manager=manager,
        key=leader_key,
        ttl_seconds=ttl_seconds,
        refresh_seconds=(int(refresh_seconds) if refresh_seconds else None),
    )
    leadership.start()
    app.extensions["job_leadership"] = leadership
    return manager
