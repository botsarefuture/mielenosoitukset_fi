"""Emergency appointment: two board votes OR (USB signature AND fresh god).

Panel launch signatures authorize only opening a named request. They cannot
grant a role, count as a board vote, or replace owner security enrollment.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from bson import ObjectId
from flask import current_app, session
from pymongo.errors import DuplicateKeyError

from mielenosoitukset_fi.utils.emergency_signatures import PANEL_DOMAIN, USB_DOMAIN, verify
from mielenosoitukset_fi.utils.system_teams import active_account, board_ids
from mielenosoitukset_fi.utils.team_governance import GovernanceConflict
from mielenosoitukset_fi.utils.time_utils import utcnow


def enabled():
    return current_app.config.get("GOD_EMERGENCY_ENABLED") is True and bool(current_app.config.get("GOD_EMERGENCY_PANEL_KEYS"))


def _candidate(db, candidate_id):
    from mielenosoitukset_fi.users.god_auth import credential_version
    user = db.users.find_one({"_id": ObjectId(str(candidate_id)), "god_candidate": True, "active": False, "god_security.policy": 1})
    version = credential_version(db, user) if user else None
    if not version:
        raise GovernanceConflict("God-tilin turvatekijöiden käyttöönotto on tehtävä ensin.")
    return user, version


def _actor(db, user, candidate_id):
    if (not user.is_authenticated or str(user.id) == str(candidate_id)
            or not active_account(db.users.find_one({"_id": user._id}))):
        raise PermissionError("Vahvistus vaatii toisen vahvistetun käyttäjätilin.")


def _fresh_god(db, user):
    from mielenosoitukset_fi.users.god_auth import valid_god_session
    return user.role == "god" and valid_god_session(db, db.users.find_one({"_id": user._id}), maximum_age=300)


def _record(db, candidate_id):
    return db.board_clearances.find_one({"user_id": str(candidate_id)}) or {}


def _state(record):
    return (record.get("team_requests") or {}).get("god_emergency") or {}


def _valid_request(db, candidate_id, request_id):
    if not enabled():
        raise PermissionError("Hätätilamenettely ei ole käytössä.")
    _, version = _candidate(db, candidate_id)
    record = _record(db, candidate_id)
    state = _state(record)
    if (state.get("id") != request_id or not state.get("expires_at") or state["expires_at"] <= utcnow()
            or state.get("credential_version") != version
            or state.get("board_roster") != sorted(board_ids(db) - {str(candidate_id)})):
        raise GovernanceConflict("Hätätilapyyntö vanhentui tai sen kohde tai hyväksyjät muuttuivat. Aloita uusi pyyntö paneelista.")
    if state.get("panel_key_id") not in current_app.config.get("GOD_EMERGENCY_PANEL_KEYS", {}):
        raise PermissionError("Paneelin luottamus on peruttu.")
    return record, state


def public_state(state):
    return {key: state.get(key) for key in ("id", "reason", "approved", "method", "expires_at", "board_votes", "challenge")}


def open_request(db, candidate_id, user, ticket):
    if not enabled():
        raise PermissionError("Hätätilamenettely ei ole käytössä.")
    _actor(db, user, candidate_id)
    if str(user.id) not in board_ids(db) and not _fresh_god(db, user):
        raise PermissionError("Pyynnön avaaminen vaatii hallituksen jäsenen tai tuoreen god-kirjautumisen.")
    target, version = _candidate(db, candidate_id)
    launch = verify(ticket, current_app.config["GOD_EMERGENCY_PANEL_KEYS"], PANEL_DOMAIN)
    now = int(utcnow().replace(tzinfo=timezone.utc).timestamp())
    if (launch.get("candidate_id") != str(target["_id"]) or not isinstance(launch.get("issued_at"), int)
            or not isinstance(launch.get("expires_at"), int) or not launch["issued_at"] <= now < launch["expires_at"]
            or launch["expires_at"] - launch["issued_at"] > 300
            or not isinstance(launch.get("launch_id"), str) or not 32 <= len(launch["launch_id"]) <= 100):
        raise ValueError("Paneelin pyyntö ei ole voimassa.")
    reason = launch.get("reason")
    if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 1000:
        raise ValueError("Kirjaa hätätilan perustelu (10–1000 merkkiä).")
    existing = _state(_record(db, candidate_id))
    if existing and not existing.get("approved") and existing.get("expires_at", utcnow()) > utcnow():
        raise GovernanceConflict("Tällä tilillä on jo voimassa oleva hätätilapyyntö.")
    try:
        db.mfa_login_challenges.insert_one({"_id": "god-panel-launch:" + hashlib.sha256(launch["launch_id"].encode()).hexdigest(),
            "kind": "god_panel_launch", "expires_at": datetime.fromtimestamp(launch["expires_at"], timezone.utc).replace(tzinfo=None)})
    except DuplicateKeyError as exc:
        raise GovernanceConflict("Paneelin pyyntö on jo käytetty.") from exc
    db.board_clearances.update_one({"user_id": str(candidate_id)}, {"$setOnInsert": {"revision": 0, "approved": False}}, upsert=True)
    record = _record(db, candidate_id)
    request_id = uuid4().hex
    expires = utcnow() + timedelta(minutes=15)
    roster = sorted(board_ids(db) - {str(candidate_id)})
    challenge = {"domain": USB_DOMAIN, "request_id": request_id, "candidate_id": str(candidate_id),
        "credential_version": version, "board_roster": roster, "reason": reason.strip(),
        "expires_at": int(expires.replace(tzinfo=timezone.utc).timestamp()), "nonce": secrets.token_urlsafe(32)}
    state = {"id": request_id, "candidate_id": str(candidate_id), "reason": reason.strip(), "credential_version": version,
        "board_roster": roster, "board_votes": {}, "challenge": challenge, "expires_at": expires,
        "panel_key_id": ticket["key_id"], "opened_by": str(user.id), "approved": False, "method": None}
    result = db.board_clearances.update_one({"_id": record["_id"], "revision": record.get("revision")},
        {"$set": {"team_requests.god_emergency": state}, "$inc": {"revision": 1}})
    if not result.matched_count:
        raise GovernanceConflict("Hyväksyntä muuttui samanaikaisesti. Aloita uusi pyyntö paneelista.")
    _audit(db, state, user, "hätätilapyynnön avaus")
    return public_state(state)


def _audit(db, state, user, action):
    db.board_audit_logs.insert_one({"user_id": state["candidate_id"], "request_id": state["id"], "action": action,
        "granted_by_id": str(user.id), "granted_by": user.username, "timestamp": utcnow(), "reason": state["reason"],
        "method": state.get("method"), "approved": state["approved"], "board_voters": sorted(state.get("board_votes") or {}),
        "god_user_id": state.get("god_user_id"), "usb_key_id": state.get("usb_key_id"), "panel_key_id": state["panel_key_id"]})


def act(db, candidate_id, user, request_id, command, proof=None):
    _actor(db, user, candidate_id)
    for _ in range(8):
        record, old = _valid_request(db, candidate_id, request_id)
        if command == "status":
            return public_state(old)
        if old["approved"]:
            if not approved_for_activation(db, candidate_id):
                raise GovernanceConflict("Vahvistus ei ole enää voimassa.")
            from mielenosoitukset_fi.utils.team_governance import _enroll
            _enroll(db, ObjectId(str(candidate_id)), "national", old)
            return public_state(old)
        state = {**old, "board_votes": dict(old["board_votes"])}
        if command in {"approve_board", "withdraw_board"}:
            if str(user.id) not in state["board_roster"]:
                raise PermissionError("Tämä vahvistus vaatii hallituksen jäsenen.")
            if command == "approve_board":
                state["board_votes"][str(user.id)] = {"username": user.username, "at": utcnow()}
            else:
                state["board_votes"].pop(str(user.id), None)
            if len(state["board_votes"]) >= 2:
                state.update(approved=True, method="two_board")
        elif command == "approve_usb_god":
            if not _fresh_god(db, user):
                raise PermissionError("USB-menettely vaatii tuoreen täydellisen god-kirjautumisen.")
            message = verify(proof, current_app.config.get("GOD_EMERGENCY_USB_KEYS"), USB_DOMAIN)
            if message != state["challenge"]:
                raise ValueError("USB-allekirjoitus ei kuulu tähän pyyntöön.")
            state.update(approved=True, method="usb_and_god", usb_key_id=proof["key_id"], usb_proof=proof,
                god_user_id=str(user.id), god_proof_id=hashlib.sha256(session["god_login_receipt"].encode()).hexdigest())
        else:
            raise ValueError("Virheellinen hätätilatoiminto.")
        update = {"team_requests.god_emergency": state}
        if state["approved"]:
            state["approved_at"] = utcnow()
            update.update(approved=True, god_appointment_emergency_id=state["id"])
            if state["method"] == "two_board":
                update["approvals"] = state["board_votes"]
                update["team_requests.national"] = {"id": state["id"], "votes": state["board_votes"], "roster": state["board_roster"],
                    "approved": True, "required": 2, "updated_at": utcnow(), "source": "god_emergency"}
        result = db.board_clearances.update_one({"_id": record["_id"], "revision": record.get("revision")},
            {"$set": update, "$inc": {"revision": 1}})
        if not result.matched_count:
            continue
        _audit(db, state, user, "god-hätätilan vahvistus" if state["approved"] else "god-hätätilan hallitusääni")
        if state["approved"]:
            from mielenosoitukset_fi.utils.team_governance import _enroll
            _enroll(db, ObjectId(str(candidate_id)), "national", state)
        return public_state(state)
    raise GovernanceConflict("Hyväksyntä muuttui samanaikaisesti. Yritä uudelleen.")


def approved_for_activation(db, candidate_id):
    state = _state(_record(db, candidate_id))
    try:
        _, state = _valid_request(db, candidate_id, state.get("id"))
    except (ValueError, PermissionError):
        return False
    if not state.get("approved"):
        return False
    if state.get("method") == "two_board":
        return len(set(state["board_votes"]) & set(state["board_roster"])) >= 2
    if state.get("method") == "usb_and_god":
        try:
            return verify(state.get("usb_proof"), current_app.config.get("GOD_EMERGENCY_USB_KEYS"), USB_DOMAIN) == state["challenge"] and bool(state.get("god_proof_id"))
        except ValueError:
            return False
    return False
