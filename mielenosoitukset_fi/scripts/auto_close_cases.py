from datetime import datetime

from bson import ObjectId

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.classes import Case
from mielenosoitukset_fi.utils.logger import logger


def _resolve(db):
    mongo = db
    now = datetime.utcnow()
    closed = 0
    checked = 0

    cursor = mongo.cases.find({"meta.closed": {"$ne": True}})
    for doc in cursor:
        checked += 1
        case = Case.from_dict(doc)
        reason = None
        demo_doc = None

        if case.case_type in {"new_demo", "demo_cancellation_request", "demo_cancelled"} and case.demo_id:
            demo_doc = mongo.demonstrations.find_one(
                {"_id": ObjectId(case.demo_id)},
                {"accepted": 1, "rejected": 1, "cancelled": 1},
            )
            if demo_doc:
                if demo_doc.get("accepted"):
                    reason = "Demo hyväksytty"
                elif demo_doc.get("rejected"):
                    reason = "Demo hylätty"
                elif demo_doc.get("cancelled"):
                    reason = "Demo peruttu"

        if not reason and case.case_type == "organization_edit_suggestion" and case.organization_id:
            org_doc = mongo.organizations.find_one({"_id": ObjectId(case.organization_id)})
            if org_doc and org_doc.get("updated_at") and case.created_at:
                if org_doc["updated_at"] >= case.created_at:
                    reason = "Organisaatiomuutokset tallennettu"

        if reason:
            case._add_history_entry(
                {
                    "timestamp": now,
                    "action": "Tapaus suljettu automaattisesti",
                    "user": "background",
                    "mech_action": "auto_close_job",
                    "metadata": {"reason": reason},
                    "meta_schema": {"reason": "string"},
                }
            )
            mongo.cases.update_one(
                {"_id": ObjectId(case._id)},
                {
                    "$set": {
                        "meta.closed": True,
                        "meta.closed_reason": reason,
                        "updated_at": now,
                    }
                },
            )
            closed += 1
    return checked, closed


def main():
    db = DatabaseManager().get_instance().get_db()
    checked, closed = _resolve(db)
    logger.info("Auto-close cases job finished", extra={"checked": checked, "closed": closed})


if __name__ == "__main__":
    main()
