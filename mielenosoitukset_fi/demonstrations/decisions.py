"""Canonical, idempotent approval decisions for demonstrations."""

from dataclasses import dataclass
from uuid import uuid4

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from mielenosoitukset_fi.demonstrations.audit import (
    log_demo_audit_entry,
    record_demo_change,
)
from mielenosoitukset_fi.utils.city_assignment import clear_city_assignment
from mielenosoitukset_fi.utils.logger import logger
from mielenosoitukset_fi.utils.time_utils import utcnow


DECISION_STATES = {
    "approved": {"approved": True, "rejected": False},
    "rejected": {"approved": False, "rejected": True},
}
DECISION_LABELS = {"approved": "Hyväksytty", "rejected": "Hylätty"}
DECISION_ACTIONS = {"approved": "approve_demo", "rejected": "reject_demo"}
DECISION_REASONS = {"approved": "demo_approved", "rejected": "demo_rejected"}

# A terminal moderation decision closes every bearer-link family. The token
# used for the decision is excluded and consumed by its route after success.
TERMINAL_TOKEN_ACTIONS = ("preview", "approve", "reject", "edit")


@dataclass(frozen=True)
class DemoDecisionResult:
    demo: dict
    decision_id: str
    changed: bool
    cases_updated: int
    tokens_revoked: int
    notification_queued: bool


def _object_id(value) -> ObjectId:
    if isinstance(value, ObjectId):
        return value
    if not ObjectId.is_valid(str(value)):
        raise ValueError("Invalid demonstration id")
    return ObjectId(str(value))


def _actor_label(actor: dict) -> str:
    return (
        actor.get("username")
        or actor.get("email")
        or actor.get("user_id")
        or "system"
    )


def _close_related_cases(db, demo_id, demo, decision, decision_meta) -> int:
    """Project the authoritative decision without clobbering a newer writer.

    The case snapshot is read before the demo authority check, and its observed
    decision id is the write precondition. A lost compare-and-set must re-read
    both records. No wall-clock ordering or multi-document transaction is assumed.
    """
    action = DECISION_ACTIONS[decision]
    label = DECISION_LABELS[decision]
    reason = DECISION_REASONS[decision]
    decision_id = decision_meta["id"]
    actor_name = _actor_label(decision_meta.get("actor") or {})
    timestamp = decision_meta["at"]
    updated = 0

    case_update = {
        "$set": {
            "status": label,
            "outcome": decision,
            "resolution": decision,
            "updated_at": timestamp,
            "meta.closed": True,
            "meta.closed_at": timestamp,
            "meta.closed_reason": reason,
            "meta.outcome": decision,
            "meta.resolution": decision,
            "meta.decision_id": decision_id,
        },
        "$push": {
            "action_logs": {
                "timestamp": timestamp,
                "admin": actor_name,
                "action_type": action,
                "note": (
                    f"Mielenosoitus {demo.get('title') or 'tuntematon'} "
                    f"({demo_id}) sai päätöksen: {label.lower()}."
                ),
            },
            "case_history": {
                "timestamp": timestamp,
                "action": label,
                "user": actor_name,
                "metadata": {
                    "decision": decision,
                    "decision_id": decision_id,
                    "source": decision_meta.get("source"),
                },
            },
        },
    }
    cases = db.cases.find({"demo_id": {"$in": [demo_id, str(demo_id)]}})
    for case_doc in cases:
        # Read the case before checking the authoritative demo decision. A
        # concurrent writer changing the case after this snapshot makes the
        # compare-and-set fail; never overwrite a newer decision blindly.
        for _ in range(8):
            previous_id = (case_doc.get("meta") or {}).get("decision_id")
            if previous_id == decision_id:
                break
            current = db.demonstrations.find_one(
                {"_id": demo_id}, {"moderation_decision.id": 1}
            )
            if not current or (
                current.get("moderation_decision") or {}
            ).get("id") != decision_id:
                break
            result = db.cases.update_one(
                {"_id": case_doc["_id"], "meta.decision_id": previous_id},
                case_update,
            )
            if result.matched_count:
                updated += result.modified_count
                break
            case_doc = db.cases.find_one({"_id": case_doc["_id"]})
            if not case_doc:
                break
        else:
            # Keep contention bounded. A retry reuses the existing decision id
            # and reconciles effects without duplicating history/notifications.
            raise RuntimeError("Case changed repeatedly during decision; retry")
    return updated


def _revoke_related_tokens(db, demo_id, decision_meta, used_token_id=None) -> int:
    token_filter = {
        "demo_id": str(demo_id),
        "action": {"$in": list(TERMINAL_TOKEN_ACTIONS)},
        "revoked": {"$ne": True},
        "used_at": None,
        "$or": [
            {"created_at": {"$lte": decision_meta["at"]}},
            {"created_at": {"$exists": False}},
        ],
    }
    if used_token_id:
        token_filter["_id"] = {"$ne": _object_id(used_token_id)}

    tokens = list(db.magic_links.find(token_filter, {"_id": 1, "action": 1}))
    if not tokens:
        return 0

    result = db.magic_links.update_many(
        {"_id": {"$in": [token["_id"] for token in tokens]}},
        {
            "$set": {
                "revoked": True,
                "revoked_at": decision_meta["at"],
                "revoked_by": _actor_label(decision_meta.get("actor") or {}),
                "revoked_reason": f"demo_{decision_meta['status']}",
                "decision_id": decision_meta["id"],
            }
        },
    )
    log_demo_audit_entry(
        demo_id,
        action="decision_tokens_revoked",
        message="Päätöksen kanssa ristiriitaiset linkit mitätöitiin",
        details={
            "decision": decision_meta["status"],
            "decision_id": decision_meta["id"],
            "token_ids": [str(token["_id"]) for token in tokens],
            "token_types": sorted({token.get("action") for token in tokens}),
        },
        actor=decision_meta.get("actor"),
    )
    return result.modified_count


def _queue_submitter_notification(
    db,
    demo,
    decision,
    decision_meta,
    email_sender,
    public_url,
) -> bool:
    submitter = db.submitters.find_one({"demonstration_id": demo["_id"]})
    recipient = (submitter or {}).get("submitter_email")
    if not recipient:
        return False

    notification_id = f"demo-decision:{decision_meta['id']}"
    try:
        db.demo_decision_notifications.insert_one(
            {
                "_id": notification_id,
                "demo_id": str(demo["_id"]),
                "decision": decision,
                "decision_id": decision_meta["id"],
                "recipient": recipient,
                "created_at": decision_meta["at"],
            }
        )
    except DuplicateKeyError:
        return False

    context = {
        "title": demo.get("title", ""),
        "date": demo.get("date", ""),
        "city": demo.get("city", ""),
        "address": demo.get("address", ""),
    }
    if decision == "approved":
        context["url"] = public_url

    try:
        email_sender.queue_email(
            template_name=f"demo_submitter_{decision}.html",
            subject=(
                "Mielenosoituksesi on hyväksytty"
                if decision == "approved"
                else "Mielenosoituksesi on hylätty"
            ),
            recipients=[recipient],
            context=context,
        )
    except Exception:
        db.demo_decision_notifications.delete_one({"_id": notification_id})
        raise

    db.demo_decision_notifications.update_one(
        {"_id": notification_id}, {"$set": {"queued_at": utcnow()}}
    )
    return True


def apply_demo_decision(
    db,
    demo_id,
    decision: str,
    *,
    actor: dict,
    source: str,
    email_sender,
    public_url: str | None = None,
    used_token_id=None,
) -> DemoDecisionResult:
    """Apply one terminal moderation decision and reconcile its side effects.

    Repeating the same decision reuses its stable decision id, so notification,
    case-history and audit side effects are not duplicated.

    Opposite decisions retain the existing last-transition-wins behavior. A
    changed result/history uses this transition's own snapshot, which may have
    been superseded by the time the caller receives it. Case projection checks
    the currently persisted decision and conditionally retries conflicting writes.
    """
    if decision not in DECISION_STATES:
        raise ValueError("Unsupported demonstration decision")

    demo_oid = _object_id(demo_id)
    target = DECISION_STATES[decision]
    now = utcnow()
    decision_meta = {
        "id": uuid4().hex,
        "status": decision,
        "at": now,
        "actor": actor,
        "source": source,
    }
    transition_filter = {
        "_id": demo_oid,
        "$or": [
            {"approved": {"$ne": target["approved"]}},
            {"rejected": {"$ne": target["rejected"]}},
            {"moderation_decision.status": {"$ne": decision}},
        ],
    }
    before = db.demonstrations.find_one_and_update(
        transition_filter,
        {
            "$set": {
                **target,
                "last_modified": now,
                "moderation_decision": decision_meta,
            }
        },
        return_document=ReturnDocument.BEFORE,
    )
    if before is None:
        current = db.demonstrations.find_one({"_id": demo_oid})
        if not current:
            raise LookupError("Demonstration not found")
        decision_meta = current.get("moderation_decision") or decision_meta
        # A different decision can commit between the conditional transition
        # and this read. Reconcile the snapshot we actually read, not a mixture
        # of the requested state and another decision's identity.
        decision = decision_meta["status"]
        status_changed = False
    else:
        status_changed = (
            before.get("approved") != target["approved"]
            or before.get("rejected") != target["rejected"]
        )
        decision_meta["notify_submitter"] = status_changed
        db.demonstrations.update_one(
            {
                "_id": demo_oid,
                "moderation_decision.id": decision_meta["id"],
            },
            {"$set": {"moderation_decision.notify_submitter": status_changed}},
        )
        # The atomic transition's before-image defines this decision's own
        # after-image. A fresh read could already belong to an opposite decision
        # and corrupt the returned result and the immutable audit/history entry.
        current = {
            **before,
            **target,
            "last_modified": now,
            "moderation_decision": decision_meta,
        }

    decision_id = decision_meta["id"]

    # A resolved demo no longer belongs to the city admins' queue.
    try:
        clear_city_assignment(db, demo_oid)
    except Exception:
        logger.exception("Failed to clear city assignment for demo %s", demo_oid)

    cases_updated = _close_related_cases(
        db, demo_oid, current, decision, decision_meta
    )
    tokens_revoked = _revoke_related_tokens(
        db, demo_oid, decision_meta, used_token_id=used_token_id
    )

    notification_queued = False
    if status_changed:
        record_demo_change(
            demo_oid,
            before,
            current,
            action=DECISION_ACTIONS[decision],
            message=(
                "Mielenosoitus hyväksyttiin"
                if decision == "approved"
                else "Mielenosoitus hylättiin"
            ),
            extra_details={
                "decision": decision,
                "decision_id": decision_id,
                "source": source,
            },
            actor=actor,
        )
    if decision_meta.get("notify_submitter"):
        notification_queued = _queue_submitter_notification(
            db,
            current,
            decision,
            decision_meta,
            email_sender,
            public_url,
        )

    return DemoDecisionResult(
        demo=current,
        decision_id=decision_id,
        changed=status_changed,
        cases_updated=cases_updated,
        tokens_revoked=tokens_revoked,
        notification_queued=notification_queued,
    )
