# mielenosoitukset_fi/utils/admin/models/Case.py
from datetime import datetime
from bson import ObjectId
from mielenosoitukset_fi.utils.database import get_database_manager, stringify_object_ids

mongo = get_database_manager()

class Case:
    """
    Admin support case model for demos, org suggestions, error reports, etc.
    Includes action logs and running number support.
    """

    COLLECTION = "cases"
    STARTING_NUM = 100001  # first case number

    def __init__(self, case_type="new_demo", demo_id=None, organization_id=None,
                 submitter_id=None, submitter=None, error_report=None, suggestion=None,
                 meta=None, action_logs=None, case_history=None, running_num=None, _id=None):
        self._id = ObjectId(_id) if _id else ObjectId()
        self.case_type = case_type
        self.demo_id = ObjectId(demo_id) if demo_id else None
        self.organization_id = ObjectId(organization_id) if organization_id else None
        self.submitter = submitter or None
        self.submitter_id = ObjectId(submitter_id) if submitter_id else None
        self.error_report = error_report or {}
        self.suggestion = suggestion or {}
        self.meta = meta or {}
        self.action_logs = action_logs or []  # list of admin actions/notes
        self.case_hisory = case_history or []
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.running_num = running_num or self._get_next_running_num()

    def _get_next_running_num(self):
        """
        Get the next running number for a new case.
        """
        last_case = mongo[self.COLLECTION].find_one(
            sort=[("running_num", -1)]
        )
        if last_case and last_case.get("running_num"):
            return last_case["running_num"] + 1
        return self.STARTING_NUM

    def add_action(self, action_type, admin_user, note=None):
        """
        Add an action log entry.
        """
        self.action_logs.append({
            "timestamp": datetime.utcnow(),
            "admin": admin_user,
            "action_type": action_type,
            "note": note
        })
        self.updated_at = datetime.utcnow()
        self.save()

    def to_dict(self):
        """
        Convert the Case object to a dictionary for MongoDB insertion or JSON serialization.
        """
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
            "case_history": self.case_hisory,
            "running_num": self.running_num,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    @classmethod
    def from_dict(cls, data):
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
            running_num=data.get("running_num")
        )

    def save(self):
        """
        Insert or update the case in the database.
        """
        self.updated_at = datetime.utcnow()
        mongo[self.COLLECTION].update_one(
            {"_id": self._id}, {"$set": self.to_dict()}, upsert=True
        )

    @classmethod
    def get(cls, case_id):
        doc = mongo[cls.COLLECTION].find_one({"_id": ObjectId(case_id)})
        if doc:
            return cls.from_dict(doc)
        return None

    @classmethod
    def create_new(cls, case_type="new_demo", demo_id=None, organization_id=None,
                   submitter_id=None, submitter=None, error_report=None, suggestion=None, meta=None):
        case = cls(
            case_type=case_type,
            demo_id=demo_id,
            organization_id=organization_id,
            submitter_id=submitter_id,
            submitter=submitter,
            error_report=error_report,
            suggestion=suggestion,
            meta=meta
        )
        case.save()
        return case
