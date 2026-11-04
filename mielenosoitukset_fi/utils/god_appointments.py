"""Two-chamber consent for appointing a new god account.

Round one needs the whole board *or* every existing god user. The chamber that
did not nominate then has 48 hours to veto, and a veto moves the decision to a
second round where 75% of all board and god users combined must approve.

The inactive ordinary-role candidate is not a god account. Only activation can
assign that role, after this consent and the complete security enrollment.
"""
import math
from datetime import timedelta
from uuid import uuid4

from bson import ObjectId
from flask import session
from pymongo.errors import DuplicateKeyError

from mielenosoitukset_fi.utils.system_teams import active_account, board_ids
from mielenosoitukset_fi.utils.team_governance import GovernanceConflict
from mielenosoitukset_fi.utils.time_utils import utcnow

VETO_WINDOW = timedelta(hours=48)
SUPERMAJORITY = 0.75
ADMIN_LINK = "https://mielenosoitukset.fi/admin/governance/clearances"


def appointment_roster(db, candidate_id):
    """Do not shrink a quorum by banning or disabling an existing approver."""
    candidate = str(candidate_id)
    board = board_ids(db) - {candidate}
    gods = {str(user["_id"]) for user in db.users.find({"role": "god"}) if str(user["_id"]) != candidate}
    return {"board": sorted(board), "gods": sorted(gods)}


def required_voters(roster):
    return set(roster.get("board") or []) | set(roster.get("gods") or [])


def supermajority(roster):
    """75% of the combined chamber, never fewer than two independent voters."""
    return max(2, math.ceil(len(required_voters(roster)) * SUPERMAJORITY))


def _other(chamber):
    return "gods" if chamber == "board" else "board"


def _blank(previous, roster, request_id):
    return {"id": request_id, "roster": roster, "votes": {}, "vetoes": {}, "chamber": None,
            "phase": "collecting", "window_ends_at": None, "approved": False, "method": None,
            "updated_at": utcnow()}


def appointment_approved(db, candidate_id):
    advance_appointment(db, candidate_id)
    record = db.board_clearances.find_one({"user_id": str(candidate_id)}) or {}
    state = (record.get("team_requests") or {}).get("god") or {}
    roster = appointment_roster(db, candidate_id)
    # Ordinary super admins do not participate. A changed electorate never
    # inherits old votes, and disabling an approver never lowers the threshold.
    if len(roster["board"]) < 2 or state.get("roster") != roster or state.get("approved") is not True:
        from mielenosoitukset_fi.utils.god_emergency import approved_for_activation
        return approved_for_activation(db, candidate_id)
    votes = set(state.get("votes") or {})
    nominating = set(roster.get(state.get("chamber")) or [])
    if state.get("method") == "unanimous":
        return bool(nominating) and nominating.issubset(votes) and not state.get("vetoes")
    if state.get("method") == "supermajority":
        return len(votes & required_voters(roster)) >= supermajority(roster)
    return False


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


def advance_appointment(db, candidate_id):
    """Close an elapsed veto window. A deadline opens a decision; it never restores access."""
    for _ in range(8):
        record = db.board_clearances.find_one({"user_id": str(candidate_id)})
        if not record:
            return None
        state = (record.get("team_requests") or {}).get("god") or {}
        if state.get("phase") != "window" or not state.get("window_ends_at") or state["window_ends_at"] > utcnow():
            return state
        roster = appointment_roster(db, candidate_id)
        if state.get("roster") != roster:
            return state
        state = {**state, "phase": "collecting", "method": "unanimous", "approved": True,
                 "window_ends_at": None, "updated_at": utcnow()}
        update = {"team_requests.god": state, "approved": True, "revision": (record.get("revision") or 0) + 1,
                  "timestamp": utcnow()}
        update["approvals"] = {uid: state["votes"][uid] for uid in roster["board"] if uid in state["votes"]}
        update["team_requests.national"] = {
            "id": state["id"], "roster": roster["board"], "votes": update["approvals"], "approved": True,
            "required": 2, "updated_at": utcnow(), "source": "unanimous_god_appointment"}
        if not db.board_clearances.update_one({"_id": record["_id"], "revision": record.get("revision")},
                                              {"$set": update}).matched_count:
            continue
        from mielenosoitukset_fi.utils.team_governance import _enroll
        _enroll(db, ObjectId(str(candidate_id)), "national", state)
        return state
    raise GovernanceConflict("Hyväksyntä muuttui samanaikaisesti. Yritä uudelleen.")


def process_appointments(db):
    """Close elapsed veto windows from the existing maintenance worker."""
    now = utcnow()
    for record in db.board_clearances.find({"team_requests.god.phase": "window",
                                            "team_requests.god.window_ends_at": {"$lte": now}}):
        advance_appointment(db, record["user_id"])


def _notify_window(db, candidate_id, state):
    """Tell the vetoing chamber that its 48-hour window is open."""
    target = db.users.find_one({"_id": ObjectId(str(candidate_id))}) or {}
    voters = [ObjectId(uid) for uid in (state.get("veto_voters") or []) if ObjectId.is_valid(uid)]
    recipients = {doc.get("email") for doc in db.users.find({"_id": {"$in": voters}}) if doc.get("email")}
    if not recipients:
        return
    from mielenosoitukset_fi.emailer.EmailJob import EmailJob
    for email in recipients:
        job = EmailJob("Mielenosoitukset.fi: god-tilin hyväksyntä odottaa veto-oikeutta", [email], body=(
            f"God-tilin ehdokas {target.get('username')} on saanut nimeävän ryhmän täyden hyväksynnän.\n"
            "Sinulla on 48 tuntia aikaa käyttää veto-oikeuttasi. Jos kukaan ei vetoa, hyväksyntä astuu voimaan.\n"
            "Veto siirtää päätöksen toiselle kierrokselle, jossa tarvitaan 75 % kaikista hallituksen ja "
            f"god-käyttäjien äänistä.\n\nKäsittele asia: {ADMIN_LINK}\n")).to_dict()
        try:
            db.email_queue.update_one({"_id": f"god-window:{state['id']}:{email.casefold()}"},
                                      {"$setOnInsert": job}, upsert=True)
        except DuplicateKeyError:
            pass


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
    if len(roster["board"]) < 2:
        raise GovernanceConflict("God-tilin hyväksyntä vaatii vähintään kaksi hallituksen jäsentä.")
    advance_appointment(db, candidate)
    try:
        db.board_clearances.update_one({"user_id": str(candidate)}, {"$setOnInsert": {
            "approved": False, "revision": 0, "created_at": utcnow()}}, upsert=True)
    except DuplicateKeyError:
        pass
    for _ in range(8):
        record = db.board_clearances.find_one({"user_id": str(candidate)})
        previous = (record.get("team_requests") or {}).get("god") or {}
        changed = previous.get("roster") != roster
        voter = str(user.id)
        state = _blank(previous, roster, uuid4().hex) if changed else {
            **previous, "votes": dict(previous.get("votes") or {}), "vetoes": dict(previous.get("vetoes") or {}),
            "updated_at": utcnow()}
        entered_window = False
        if state.get("chamber") is None:
            state["chamber"] = "gods" if voter in roster["gods"] and voter not in roster["board"] else "board"
        active, other = state["chamber"], _other(state["chamber"])
        state["veto_voters"] = sorted(set(roster[other]) - set(roster[active]))
        if state["phase"] == "collecting":
            state["required"] = len(roster[active])
            if voter in roster[active]:
                if approve:
                    state["votes"][voter] = {"username": user.username, "at": utcnow(), "role": user.role}
                else:
                    state["votes"].pop(voter, None)
            elif voter in state["veto_voters"] and not approve:
                # An early veto still counts and starts the second round.
                state["vetoes"][voter] = {"username": user.username, "at": utcnow(), "role": user.role,
                                          "reason": "Veto ennen ensimmäisen kierroksen päätöstä"}
                state.update(phase="second_round", votes={}, window_ends_at=None)
            if state["phase"] == "collecting" and set(roster[active]).issubset(set(state["votes"])):
                if state["veto_voters"]:
                    state.update(phase="window", window_ends_at=utcnow() + VETO_WINDOW,
                                 required=supermajority(roster))
                    entered_window = True
                else:
                    state.update(method="unanimous", approved=True)
        elif state["phase"] == "window":
            state["required"] = supermajority(roster)
            if voter in state["veto_voters"] and not approve:
                state["vetoes"][voter] = {"username": user.username, "at": utcnow(), "role": user.role,
                                          "reason": "Veto 48 tunnin harkinta-aikana"}
                state.update(phase="second_round", votes={}, window_ends_at=None)
        if state["phase"] == "second_round":
            state["required"] = supermajority(roster)
            if approve:
                state["votes"][voter] = {"username": user.username, "at": utcnow(), "role": user.role}
            else:
                state["votes"].pop(voter, None)
            reached = len(set(state["votes"]) & required_voters(roster)) >= state["required"]
            state.update(method="supermajority" if reached else None, approved=reached)
        update = {"team_requests.god": state, "revision": (record.get("revision") or 0) + 1, "timestamp": utcnow()}
        if state["approved"]:
            update["approved"] = True
            update["approvals"] = {uid: state["votes"][uid] for uid in roster["board"] if uid in state["votes"]}
            update["team_requests.national"] = {
                "id": state["id"], "roster": roster["board"], "votes": update["approvals"], "approved": True,
                "required": 2, "updated_at": utcnow(), "source": "god_appointment_consent"}
        result = db.board_clearances.update_one({"_id": record["_id"], "revision": record.get("revision")},
                                                {"$set": update})
        if not result.matched_count:
            continue
        db.board_audit_logs.insert_one({
            "user_id": str(candidate), "action": "god-tilin hyväksyntä" if approve else "god-hyväynnän peruminen",
            "granted_by_id": voter, "granted_by": user.username, "timestamp": utcnow(), "request_id": state["id"],
            "roster": roster, "approval_count": len(state["votes"]), "required": state.get("required"),
            "approved": state["approved"], "phase": state["phase"], "vetoes": sorted(state["vetoes"]),
            "god_receipt": session.get("god_login_receipt") is not None if user.role == "god" else False})
        if entered_window:
            _notify_window(db, candidate, state)
        if state["approved"] and state["phase"] != "window":
            from mielenosoitukset_fi.utils.team_governance import _enroll
            _enroll(db, candidate, "national", state)
        return state
    raise GovernanceConflict("Hyväksyntä muuttui samanaikaisesti. Yritä uudelleen.")
