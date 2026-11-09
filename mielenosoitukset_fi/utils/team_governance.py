"""Quorum-controlled admission to the two protected organizations."""
from uuid import uuid4
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from mielenosoitukset_fi.utils.system_teams import active_account, board_ids, team_ids
from mielenosoitukset_fi.utils.time_utils import utcnow
from datetime import timedelta


class GovernanceConflict(ValueError):
    pass


def override_role(db, user):
    from mielenosoitukset_fi.utils.system_teams import olivia_user_id
    if not user.is_authenticated or not user.is_active or not user.confirmed:
        return None
    if str(user.id) == olivia_user_id():
        return "olivia"
    if user.role == "god":
        from mielenosoitukset_fi.users.god_auth import valid_god_session
        doc = db.users.find_one({"_id": user._id})
        if valid_god_session(db, doc, maximum_age=300):
            return "god"
    return None


def cast_joint_override(db, candidate_id, user, kind):
    role = override_role(db, user)
    candidate = str(ObjectId(str(candidate_id)))
    if not role or candidate == str(user.id):
        raise PermissionError("Ohitus vaatii Olivian ja erillisen god-tilin hyväksynnän.")
    if kind not in {"national", "board"} or kind not in team_ids():
        raise ValueError("Virheellinen ylläpitotiimi.")
    target = db.users.find_one({"_id": ObjectId(candidate)})
    if not target or not active_account(target):
        raise ValueError("Käyttäjätili ei ole käytössä tai vahvistettu.")
    try:
        db.board_clearances.update_one({"user_id": candidate}, {"$setOnInsert": {"approved":False,"revision":0,"created_at":utcnow()}},upsert=True)
    except DuplicateKeyError:
        pass
    for _ in range(8):
        record = db.board_clearances.find_one({"user_id":candidate})
        previous = request_state(record,kind)
        if previous.get("approved"):
            _enroll(db, ObjectId(candidate), kind, previous)
            return previous
        now = utcnow()
        approvals = {key:value for key,value in (previous.get("override_votes") or {}).items()
                     if value.get("at") and value["at"] > now-timedelta(minutes=10)}
        approvals[role] = {"user_id":str(user.id),"username":user.username,"at":now}
        complete = set(approvals)=={"olivia","god"} and approvals["olivia"]["user_id"] != approvals["god"]["user_id"]
        state = {**previous,"id":previous.get("id") or uuid4().hex,"roster":previous.get("roster") or sorted(board_ids(db)),
                 "override_votes":approvals,"approved":complete,"updated_at":now,"required":2 if kind=="national" else len(board_ids(db))}
        update = {f"team_requests.{kind}":state,"revision":(record.get("revision") or 0)+1,"timestamp":now}
        if complete and kind=="national":
            update.update(approved=True, approvals={value["user_id"]:value for value in approvals.values()})
        changed = db.board_clearances.update_one({"_id":record["_id"],"revision":record.get("revision")},{"$set":update})
        if not changed.matched_count:
            continue
        if complete:
            _enroll(db,ObjectId(candidate),kind,state)
        db.board_audit_logs.insert_one({"user_id":candidate,"action":"yhteinen ohitus" if complete else "ohituksen osahyväksyntä",
            "granted_by":user.username,"granted_by_id":str(user.id),"team":kind,"request_id":state["id"],
            "override_role":role,"approved":complete,"timestamp":now})
        return state
    raise GovernanceConflict("Hyväksyntä muuttui samanaikaisesti. Yritä uudelleen.")


def request_state(record, kind):
    return ((record or {}).get("team_requests") or {}).get(kind) or {}


def _enroll(db, candidate, kind, state):
    organization = team_ids().get(kind)
    if not organization:
        raise GovernanceConflict("Ylläpitotiimien asetukset puuttuvat.")
    db.memberships.update_one(
        {"user_id": candidate, "organization_id": organization},
        {"$set": {"governance_approved": True,
                  "grant_source": "emergency_god_appointment" if state.get("method") in {"two_board", "usb_and_god"} else "board_approval",
                  "approval_request_id": state["id"]},
         "$setOnInsert": {"role": "member", "permissions": [], "created_at": utcnow()}}, upsert=True,
    )
    if kind == "national":
        from mielenosoitukset_fi.users.god_auth import activate_enrolled_candidate
        activate_enrolled_candidate(db, candidate)


def cast_vote(db, candidate_id, voter_id, kind, approve):
    if kind not in {"national", "board"} or type(approve) is not bool:
        raise ValueError("Virheellinen hyväksyntäpyyntö.")
    candidate, voter = str(ObjectId(str(candidate_id))), str(ObjectId(str(voter_id)))
    roster = board_ids(db)
    if voter not in roster or voter == candidate:
        raise PermissionError("Hyväksyntä vaatii toisen hallituksen jäsenen.")
    target = db.users.find_one({"_id": ObjectId(candidate)})
    if target and target.get("role") == "god" and not approve:
        raise GovernanceConflict("God-tilin käyttöoikeus keskeytetään tai poistetaan turvatapauksessa.")
    if not target or not active_account(target) and not target.get("god_candidate"):
        raise ValueError("Käyttäjätili ei ole käytössä tai vahvistettu.")
    if kind not in team_ids():
        raise GovernanceConflict("Ylläpitotiimien asetukset puuttuvat.")
    actor = db.users.find_one({"_id": ObjectId(voter)}, {"username": 1})
    if not active_account(db.users.find_one({"_id": ObjectId(voter)})):
        raise PermissionError("Hyväksyjän tilin on oltava käytössä ja vahvistettu.")
    try:
        db.board_clearances.update_one({"user_id": candidate}, {"$setOnInsert": {
            "approved": False, "revision": 0, "created_at": utcnow(),
        }}, upsert=True)
    except DuplicateKeyError:
        pass  # Another voter created this uniquely keyed user's record.
    for _ in range(8):
        record = db.board_clearances.find_one({"user_id": candidate})
        previous = request_state(record, kind)
        if (kind == "national" and previous.get("approved")
                and previous.get("source") in {"unanimous_god_appointment", "god_appointment_consent"}):
            # A routine board vote must not replace the appointment evidence
            # used to authorize the nominee at and after activation.
            return previous
        if previous.get("approved") and kind == "board":
            if not approve:
                raise GovernanceConflict("Hallituksen jäsenyyttä ei poisteta yksittäisellä äänellä.")
            _enroll(db, ObjectId(candidate), kind, previous)
            return previous
        required_roster = previous.get("roster") or sorted(roster)
        if kind == "board" and set(required_roster) != roster:
            raise GovernanceConflict("Hallituksen kokoonpano muuttui. Hyväksyntäkierros on tarkistettava.")
        votes = dict(previous.get("votes") or {})
        if approve:
            votes[voter] = {"username": actor.get("username"), "at": utcnow()}
        else:
            votes.pop(voter, None)
        eligible_votes = set(votes) & roster - {candidate}
        accepted = set(required_roster).issubset(eligible_votes) if kind == "board" else len(eligible_votes) >= 2
        state = {"id": previous.get("id") or uuid4().hex, "roster": required_roster,
                 "votes": votes, "approved": bool(accepted), "updated_at": utcnow(),
                 "required": len(required_roster) if kind == "board" else 2}
        update = {f"team_requests.{kind}": state, "revision": (record.get("revision") or 0) + 1,
                  "timestamp": utcnow(), "granted_by": actor.get("username"), "granted_by_id": voter}
        if kind == "national":
            update.update(approved=bool(accepted), approvals=votes)
        changed = db.board_clearances.update_one({"_id": record["_id"], "revision": record.get("revision")}, {"$set": update})
        if not changed.matched_count:
            continue
        # Reconcile from the authoritative request, so a stale concurrent vote
        # cannot create a live grant after a newer withdrawal won.
        if accepted:
            _enroll(db, ObjectId(candidate), kind, state)
        # A withdrawal invalidates live access through clearance_approved().
        # Retain the admitted membership: deleting it here could race with a
        # newer successful vote in this separate collection.
        db.board_audit_logs.insert_one({"user_id": candidate, "action": "hyväksyntä" if approve else "hyväksynnän peruminen",
            "granted_by": actor.get("username"), "granted_by_id": voter, "timestamp": utcnow(),
            "team": kind, "request_id": state["id"], "approval_count": len(eligible_votes), "required": state["required"], "approved": accepted})
        return state
    raise GovernanceConflict("Hyväksyntä muuttui samanaikaisesti. Yritä uudelleen.")
