"""Admin support Case model (demos, organisation suggestions, error reports …) 
Refactored to preserve original timestamps instead of blindly overwriting them
with datetime.utcnow() when loading from DB.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId

from mielenosoitukset_fi.utils.database import get_database_manager

mongo = get_database_manager()


class Case:
    """Persisted admin‑side support case.

    Attributes
    ----------
    running_num
        Sequential public number, starts from :pyattr:`STARTING_NUM`.
    created_at / updated_at
        UTC datetimes; existing values from the database are preserved on load.
    """

    COLLECTION = "cases"
    STARTING_NUM = 100_001

    # ---------------------------------------------------------------------
    # Construction helpers
    # ---------------------------------------------------------------------
    def __init__(
        self,
        case_type: str = "new_demo",
        demo_id: Optional[str | ObjectId] = None,
        organization_id: Optional[str | ObjectId] = None,
        submitter_id: Optional[str | ObjectId] = None,
        submitter: Optional[Dict[str, Any]] = None,
        error_report: Optional[Dict[str, Any]] = None,
        suggestion: Optional[Dict[str, Any]] = None,
        meta: Optional[Dict[str, Any]] = None,
        action_logs: Optional[List[Dict[str, Any]]] = None,
        case_history: Optional[List[Dict[str, Any]]] = None,
        running_num: Optional[int] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        _id: Optional[str | ObjectId] = None,
    ) -> None:
        # IDs ----------------------------------------------------------------
        self._id: ObjectId = ObjectId(_id) if _id else ObjectId()
        self.demo_id: Optional[ObjectId] = ObjectId(demo_id) if demo_id else None
        self.organization_id: Optional[ObjectId] = (
            ObjectId(organization_id) if organization_id else None
        )
        self.submitter_id: Optional[ObjectId] = (
            ObjectId(submitter_id) if submitter_id else None
        )

        # Core data ----------------------------------------------------------
        self.case_type: str = case_type
        self.submitter: Optional[Dict[str, Any]] = submitter
        self.error_report: Dict[str, Any] = error_report or {}
        self.suggestion: Dict[str, Any] = suggestion or {}
        self.meta: Dict[str, Any] = meta or {}

        # Logs ---------------------------------------------------------------
        self.action_logs: List[Dict[str, Any]] = action_logs or []
        self.case_history: List[Dict[str, Any]] = case_history or []

        # Timestamps ---------------------------------------------------------
        now = datetime.utcnow()
        self.created_at: datetime = created_at or now
        self.updated_at: datetime = updated_at or now

        # Running number -----------------------------------------------------
        self.running_num: int = running_num or self._get_next_running_num()

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------
    def _get_next_running_num(self) -> int:
        """Return next sequential running number (atomic enough for admin use)."""
        last = mongo[self.COLLECTION].find_one(sort=[("running_num", -1)])
        return (last.get("running_num", self.STARTING_NUM - 1) + 1) if last else self.STARTING_NUM

    def _touch(self) -> None:
        """Update *updated_at* and persist current in‑memory state to MongoDB."""
        self.updated_at = datetime.utcnow()
        mongo[self.COLLECTION].update_one({"_id": self._id}, {"$set": self.to_dict()}, upsert=True)

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """Convert to a Mongo‑serialisable dict."""
        return {
            "_id": self._id,
            "type": self.case_type,
            "demo_id": self.demo_id,
            "organization_id": self.organization_id,
            "submitter_id": self.submitter_id,
            "submitter": self.submitter,
            "error_report": self.error_report,
            "suggestion": self.suggestion,
            "meta": self.meta,
            "action_logs": self.action_logs,
            "case_history": self.case_history,
            "running_num": self.running_num,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    # ------------------------------------------------------------------ class‑methods
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Case":
        """Instantiate from MongoDB document."""
        return cls(
            _id=data.get("_id"),
            case_type=data.get("type", "new_demo"),
            demo_id=data.get("demo_id"),
            organization_id=data.get("organization_id"),
            submitter_id=data.get("submitter_id"),
            submitter=data.get("submitter"),
            error_report=data.get("error_report"),
            suggestion=data.get("suggestion"),
            meta=data.get("meta"),
            action_logs=data.get("action_logs"),
            case_history=data.get("case_history"),
            running_num=data.get("running_num"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    @classmethod
    def get(cls, case_id: str | ObjectId) -> Optional["Case"]:
        doc = mongo[cls.COLLECTION].find_one({"_id": ObjectId(case_id)})
        return cls.from_dict(doc) if doc else None

    @classmethod
    def create_new(
        cls,
        case_type: str = "new_demo",
        demo_id: Optional[str | ObjectId] = None,
        organization_id: Optional[str | ObjectId] = None,
        submitter_id: Optional[str | ObjectId] = None,
        submitter: Optional[Dict[str, Any]] = None,
        error_report: Optional[Dict[str, Any]] = None,
        suggestion: Optional[Dict[str, Any]] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> "Case":
        case = cls(
            case_type=case_type,
            demo_id=demo_id,
            organization_id=organization_id,
            submitter_id=submitter_id,
            submitter=submitter,
            error_report=error_report,
            suggestion=suggestion,
            meta=meta,
        )
        case._touch()
        return case

    # ---------------------------------------------------------------------
    # Mutators that auto‑persist
    # ---------------------------------------------------------------------
    def add_action(self, action_type: str, admin_user: str, note: str | None = None) -> None:
        self.action_logs.append({
            "timestamp": datetime.utcnow(),
            "admin": admin_user,
            "action_type": action_type,
            "note": note,
        })
        self._touch()

    def _add_history_entry(self, entry: Dict[str, Any]) -> None:
        self.case_history.append(entry)
        self._touch()

    # ---------------------------------------------------------------------
    # Convenience dunder methods
    # ---------------------------------------------------------------------
    def __repr__(self) -> str:  # pragma: no cover
        return f"<Case {self.running_num} ({self.case_type})>"
