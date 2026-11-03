"""Unanimous, fixed-roster consent for appointing a new god account.

The inactive ordinary-role candidate is not a god account. Only activation can
assign that role, after this consent and the complete security enrollment.
"""
from uuid import uuid4

from bson import ObjectId
from flask import session
from pymongo.errors import DuplicateKeyError

from mielenosoitukset_fi.utils.system_teams import (
    SUPER_ROLES, active_account, approved_members, board_ids, user_team_access,
)
from mielenosoitukset_fi.utils.team_governance import GovernanceConflict
from mielenosoitukset_fi.utils.time_utils import utcnow


def appointment_roster(db, candidate_id):
    """Do not shrink a quorum by banning or disabling an existing approver."""
    candidate = str(candidate_id)
    board = board_ids(db) - {candidate}
    super_admins, gods = set(), set()
    for user in db.users.find({"$or": [{"global_admin": True}, {"role": {"$in": list(SUPER_ROLES)}}]}):
        uid = str(user["_id"])
        if uid == candidate:
            continue
        if user.get("role") == "god":
            gods.add(uid)
        if not user.get("governance_managed") or "national" in user_team_access(db, uid):
            super_admins.add(uid)
    for user in approved_members(db, "national", include_inactive=True):
        uid = str(user["_id"])
        if uid != candidate and "national" in user_team_access(db, uid):
            super_admins.add(uid)
    return {"board": sorted(board), "super_admins": sorted(super_admins), "gods": sorted(gods)}


def required_voters(roster):
    return set().union(*(set(roster.get(group) or []) for group in ("board", "super_admins", "gods")))


def appointment_approved(db, candidate_id):
    record = db.board_clearances.find_one({"user_id": str(candidate_id)}) or {}
    state = (record.get("team_requests") or {}).get("god") or {}
    roster = appointment_roster(db, candidate_id)
    # Two board approvals for new super-admin access remain mandatory. An empty
    # existing-god group permits the first appointment; other groups cannot be
    # empty or be replaced by an ordinary two-person/joint override.
    return bool(state.get("approved") is True and state.get("method") == "unanimous"
                and len(roster["board"]) >= 2 and roster["super_admins"]
                and state.get("roster") == roster
                and required_voters(roster).issubset(set(state.get("votes") or {})))


def can_vote(db, user, candidate_id):
    if (not user.is_authenticated or str(user.id) == str(candidate_id)
            or not active_account(db.users.find_one({"_id": user._id}))):
        return False
    if str(user.id) not in required_voters(appointment_roster(db, candidate_id)):
        return False
    if user.role == "god":
        from mielenosoitukset_fi.users.god_auth import valid_god_session
        return valid_god_session(db, db.users.find_one({"_id": user._id}), maximum_age=300)
    return True


def cast_appointment_vote(db, candidate_id, user, approve):
    if type(approve) is not bool:
        raise ValueError("Virheellinen hyväksyntäpyyntö.")
    candidate = ObjectId(str(candidate_id))
    target = db.users.find_one({"_id": candidate, "god_candidate": True, "active": False})
    if not target:
        raise GovernanceConflict("Tili ei ole käyttöönottoa odottava god-tiliehdokas.")
    if not can_vote(db, user, candidate):
        raise PermissionError("God-tilin hyväksyntä vaatii nykyisen hyväksyjän. God-tililtä vaaditaan tuore täysi kirjautuminen.")
    roster = appointment_roster(db, candidate)
    if len(roster["board"]) < 2 or not roster["super_admins"]:
        raise GovernanceConflict("God-tilin hyväksyntä vaatii määritetyn hallituksen ja superylläpitäjät.")
    try:
        db.board_clearances.update_one({"user_id": str(candidate)}, {"$setOnInsert": {
            "approved": False, "revision": 0, "created_at": utcnow()}}, upsert=True)
    except DuplicateKeyError:
        pass
    for _ in range(8):
        record = db.board_clearances.find_one({"user_id": str(candidate)})
        previous = (record.get("team_requests") or {}).get("god") or {}
        # A changed electorate starts a new request with no inherited votes,
        # rather than turning a smaller electorate into an automatic approval.
        changed_roster = previous.get("roster") != roster
        votes = {} if changed_roster else dict(previous.get("votes") or {})
        voter = str(user.id)
        if approve:
            votes[voter] = {"username": user.username, "at": utcnow(), "role": user.role}
        else:
            votes.pop(voter, None)
        accepted = required_voters(roster).issubset(set(votes))
        state = {"id": uuid4().hex if changed_roster else previous["id"], "method": "unanimous", "roster": roster,
                 "votes": votes, "approved": accepted, "required": len(required_voters(roster)), "updated_at": utcnow()}
        update = {"team_requests.god": state, "revision": (record.get("revision") or 0) + 1, "timestamp": utcnow()}
        if accepted:
            update.update(approved=True, approvals={uid: votes[uid] for uid in roster["board"]})
            update["team_requests.national"] = {
                "id": state["id"], "roster": roster["board"], "votes": {uid: votes[uid] for uid in roster["board"]},
                "approved": True, "required": 2, "updated_at": utcnow(), "source": "unanimous_god_appointment",
            }
        result = db.board_clearances.update_one({"_id": record["_id"], "revision": record.get("revision")}, {"$set": update})
        if not result.matched_count:
            continue
        db.board_audit_logs.insert_one({"user_id": str(candidate), "action": "god-tilin hyväksyntä" if approve else "god-hyväksynnän peruminen",
            "granted_by_id": voter, "granted_by": user.username, "timestamp": utcnow(), "request_id": state["id"],
            "roster": roster, "approval_count": len(votes), "required": state["required"], "approved": accepted,
            "god_receipt": session.get("god_login_receipt") is not None if user.role == "god" else False})
        if accepted:
            from mielenosoitukset_fi.utils.team_governance import _enroll
            _enroll(db, candidate, "national", state)
        return state
    raise GovernanceConflict("Hyväksyntä muuttui samanaikaisesti. Yritä uudelleen.")
