"""Audited incident decisions. A review deadline never restores account access.

Votes and the decision are a single revision-checked document. Effects are
idempotent and reconciled by the existing worker after a process interruption.
No approval is inferred from an email, organization invitation or root operator.
"""
import hashlib
from datetime import timedelta
from uuid import uuid4

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from mielenosoitukset_fi.emailer.EmailJob import EmailJob
from mielenosoitukset_fi.utils.system_teams import active_account, board_ids, team_ids
from mielenosoitukset_fi.utils.team_governance import GovernanceConflict
from mielenosoitukset_fi.utils.time_utils import utcnow

DECISIONS = {"suspend", "extend", "restore", "remove_role", "lockdown", "reopen"}
TERMINAL = {"restored", "role_removed"}


def person_id(doc):
    """The regular owner and their separately enrolled god account are one voter."""
    return str((doc.get("god_security") or {}).get("owner_id") or doc["_id"])


def suspended(doc):
    return bool((doc or {}).get("security_suspension", {}).get("active"))


def link_suspended(db, link):
    ids = [link.get("created_by_id"), (link.get("intended_recipient") or {}).get("user_id")]
    return any(suspended(doc) for doc in db.users.find({"_id": {"$in": [ObjectId(str(uid)) for uid in ids if ObjectId.is_valid(str(uid))]}}))


def protected_account(db, doc):
    return bool(doc and (doc.get("role") == "god" or doc.get("god_candidate")
                        or str(doc["_id"]) in board_ids(db) or suspended(doc)))


def actor_access(db, actor):
    if not actor.is_authenticated:
        raise PermissionError("Kirjaudu sisään hallituksen jäsenenä tai god-käyttäjänä.")
    doc = db.users.find_one({"_id": actor._id})
    if not active_account(doc):
        raise PermissionError("Käyttäjätilin käyttöoikeus on keskeytetty.")
    board = str(actor.id) in board_ids(db)
    god = doc.get("role") == "god"
    if not board and not god:
        raise PermissionError("Toiminto vaatii hallituksen jäsenen tai god-käyttäjän.")
    return doc, board, god


def _fresh_god(db, doc):
    from mielenosoitukset_fi.users.god_auth import valid_god_session
    return doc.get("role") == "god" and valid_god_session(db, doc, maximum_age=300)


def _reason(value):
    if not isinstance(value, str) or not 10 <= len(value.strip()) <= 1000:
        raise ValueError("Kirjaa perustelu (10–1000 merkkiä).")
    return value.strip()


def _roster(db, target):
    affected = person_id(target) if target else None
    # Disabled reviewers stay in the electorate. Disabling an account cannot
    # lower the threshold; an affected person never votes on their own case.
    return {str(doc["_id"]): person_id(doc)
            for doc in db.users.find({"_id": {"$in": [ObjectId(uid) for uid in board_ids(db)]}})
            if person_id(doc) != affected}


def _fingerprint(db, doc):
    if doc.get("role") == "god":
        from mielenosoitukset_fi.users.god_auth import credential_version
        return credential_version(db, doc)
    return hashlib.sha256((doc.get("password_hash") or "").encode()).hexdigest()


def open_case(db, actor, target_id, reason, *, lockdown=False):
    actor_access(db, actor)
    reason = _reason(reason)
    target = None
    if not lockdown:
        target = db.users.find_one({"_id": ObjectId(str(target_id))})
        if not target:
            raise ValueError("Käyttäjää ei löytynyt.")
        if suspended(target):
            raise GovernanceConflict("Tilillä on jo avoin keskeytystapaus.")
    now = utcnow()
    case = {"_id": uuid4().hex, "revision": 0, "kind": "lockdown" if lockdown else "account",
            "target_id": str(target["_id"]) if target else None,
            "target_name": target.get("username") if target else "Julkinen sivusto",
            "affected_person": person_id(target) if target else None,
            "reason": reason, "opened_by": str(actor.id), "created_at": now,
            "status": "pending", "events": [], "credential_before": _fingerprint(db, target) if target else None}
    db.security_cases.insert_one(case)
    return decide(db, case["_id"], actor, "lockdown" if lockdown else "suspend", reason)


def decide(db, case_id, actor, action, reason, *, recovery_confirmed=False, hearing=None):
    doc, is_board, _ = actor_access(db, actor)
    if action not in DECISIONS:
        raise ValueError("Virheellinen turvatoiminto.")
    reason = _reason(reason)
    for _ in range(8):
        case = db.security_cases.find_one({"_id": case_id})
        if not case:
            raise ValueError("Turvatapausta ei löytynyt.")
        if case.get("effect_pending"):
            reconcile_case(db, case)
            raise GovernanceConflict("Edellinen päätös viimeistellään. Päivitä näkymä.")
        if person_id(doc) == case["affected_person"]:
            raise PermissionError("Et voi hyväksyä omaa turvatapaustasi toisellakaan tilillä.")
        target = db.users.find_one({"_id": ObjectId(case["target_id"])}) if case["target_id"] else None
        if case["status"] in TERMINAL:
            raise GovernanceConflict("Turvatapaus on suljettu.")
        allowed = {"lockdown"} if case["kind"] == "lockdown" and case["status"] == "pending" else (
            {"reopen"} if case["kind"] == "lockdown" else (
                {"suspend"} if case["status"] == "pending" else {"extend", "restore", "remove_role"}))
        if action not in allowed:
            raise GovernanceConflict("Toiminto ei kuulu tapauksen nykyiseen vaiheeseen.")
        if target and case["status"] != "pending" and (target.get("security_suspension") or {}).get("case_id") != case_id:
            raise GovernanceConflict("Tilin keskeytystapaus on muuttunut.")
        roster = _roster(db, target)
        voters = set(roster.values())
        required = max(2, len(voters) // 2 + 1) if action == "remove_role" else 2
        urgent = action in {"suspend", "lockdown", "reopen"}
        god = urgent and _fresh_god(db, doc)
        if not is_board and not god:
            raise PermissionError("Päätös vaatii hallitusäänet tai kiireellisessä toimessa tuoreen täyden god-kirjautumisen.")
        if action == "restore":
            if recovery_confirmed is not True or not hearing or not 10 <= len(hearing.strip()) <= 2000:
                raise ValueError("Kirjaa kuuleminen ja vahvista omistajan tekemä tunnusten palautus.")
            version = _fingerprint(db, target)
            if not version or version == case["credential_before"]:
                raise GovernanceConflict("Omistajan tunnukset on uusittava ennen käyttöoikeuden palautusta.")
        if action == "remove_role" and (not hearing or not 10 <= len(hearing.strip()) <= 2000):
            raise ValueError("Kirjaa kuuleminen tai perusteltu kuulemisyritys ennen pysyvää päätöstä.")
        proposal = case.get("proposal") or {}
        # Bind each vote to the exact decision, reason, hearing, electorate and
        # current recovered credentials. A conflicting proposal discards votes.
        material = {"action": action, "reason": reason, "roster": roster,
                    "hearing": (hearing or "").strip(), "credential": _fingerprint(db, target) if action == "restore" else None}
        votes = dict(proposal.get("votes") or {}) if proposal.get("decision") == material else {}
        if is_board:
            votes[str(actor.id)] = {"person_id": person_id(doc), "username": actor.username, "at": utcnow()}
        count = len({v["person_id"] for uid, v in votes.items() if uid in roster})
        approved = god or count >= required
        event = {"id": uuid4().hex, "action": action, "reason": reason, "actor_id": str(actor.id),
                 "actor_name": actor.username, "at": utcnow(), "approved": approved,
                 "method": "fresh_god" if god else "board", "votes": votes, "required": required,
                 "hearing": material["hearing"], "roster": roster}
        update = {"proposal": {"decision": material, "votes": votes, "required": required}, "updated_at": utcnow()}
        if approved:
            update["effect_pending"] = event
        changed = db.security_cases.update_one({"_id": case_id, "revision": case["revision"]},
            {"$set": update, "$inc": {"revision": 1}, "$push": {"events": event}})
        if not changed.matched_count:
            continue
        reconcile_case(db, db.security_cases.find_one({"_id": case_id}))
        return db.security_cases.find_one({"_id": case_id})
    raise GovernanceConflict("Päätös muuttui samanaikaisesti. Päivitä näkymä.")


def _revoke(db, target, case_id):
    uid = target["_id"]
    db.api_tokens.update_many({"user_id": {"$in": [uid, str(uid)]}},
                             {"$set": {"revoked_at": utcnow(), "security_case_id": case_id}})
    db.mfa_login_challenges.delete_many({"user_id": {"$in": [uid, str(uid)]}})
    db.magic_links.update_many({"$or": [{"intended_recipient.user_id": {"$in": [uid, str(uid)]}},
                                        {"created_by_id": {"$in": [uid, str(uid)]}}]},
                              {"$set": {"revoked": True, "security_case_id": case_id}})


def reconcile_case(db, case):
    """Finish an approved effect without turning a worker retry into a new vote."""
    event = case.get("effect_pending")
    if not event:
        return
    action, now = event["action"], utcnow()
    status = {"suspend": "suspended", "extend": "suspended", "restore": "restored",
              "remove_role": "role_removed", "lockdown": "locked", "reopen": "restored"}[action]
    if case["kind"] == "lockdown":
        current = db.panic.find_one({"_id": "security-lockdown"}) or {}
        if event["id"] not in current.get("applied_events", []):
            if current.get("panic") and current.get("case_id") != case["_id"]:
                raise GovernanceConflict("Sivustolla on toinen aktiivinen sulkutapaus.")
            predicate = {"_id": "security-lockdown", "event_id": current.get("event_id")}
            try:
                changed = db.panic.update_one(predicate, {"$set": {
                    "name": "security", "panic": action == "lockdown", "case_id": case["_id"],
                    "event_id": event["id"], "updated_at": now}, "$addToSet": {"applied_events": event["id"]}}, upsert=not current)
            except DuplicateKeyError as exc:
                raise GovernanceConflict("Sulkutila muuttui. Päivitä näkymä.") from exc
            if not changed.matched_count and not changed.upserted_id:
                raise GovernanceConflict("Sulkutila muuttui. Päivitä näkymä.")
            if action == "reopen":
                db.panic.update_many({"name": "global"}, {"$set": {"panic": False}})
    else:
        uid = ObjectId(case["target_id"])
        target = db.users.find_one({"_id": uid})
        hold = (target or {}).get("security_suspension") or {}
        if not target:
            raise GovernanceConflict("Kohdetili puuttuu. Turvatapaus vaatii selvityksen.")
        if action == "suspend":
            result = db.users.update_one({"_id": uid, "security_suspension.active": {"$ne": True}, "security_applied_effects": {"$ne": event["id"]}},
                {"$set": {"security_suspension": {"active": True, "case_id": case["_id"], "since": now}},
                 "$inc": {"auth_epoch": 1}, "$addToSet": {"security_applied_effects": event["id"]}})
            if not result.matched_count and event["id"] not in target.get("security_applied_effects", []) and hold.get("case_id") != case["_id"]:
                raise GovernanceConflict("Tilillä on toinen keskeytystapaus. Uutta päätöstä ei suoritettu.")
            if result.matched_count:
                _revoke(db, target, case["_id"])
        elif action in {"restore", "remove_role"}:
            updates = {"security_suspension.active": action == "remove_role",
                       "security_suspension.decision_id": event["id"]}
            if action == "remove_role":
                updates.update(role="user", global_admin=False, global_permissions=[], governance_managed=True)
            # Revoke before releasing the hold. Otherwise a newly issued token
            # could be mistaken for an old token by a retrying worker.
            if event["id"] not in target.get("security_applied_effects", []):
                _revoke(db, target, case["_id"])
            db.users.update_one({"_id": uid, "security_suspension.case_id": case["_id"],
                                 "security_applied_effects": {"$ne": event["id"]}},
                                {"$set": updates, "$inc": {"auth_epoch": 1}, "$addToSet": {"security_applied_effects": event["id"]}})
            if action == "remove_role":
                db.memberships.update_many({"user_id": {"$in": [uid, str(uid)]},
                    "organization_id": {"$in": [*team_ids().values(), *(str(v) for v in team_ids().values())]}},
                    {"$set": {"governance_approved": False, "removed_by_security_case": case["_id"]}})
                db.board_clearances.update_many({"user_id": str(uid)}, {"$set": {"approved": False, "security_removed": case["_id"]}})
    update = {"status": status, "effect_pending": None, "proposal": {}, "updated_at": now}
    if action in {"suspend", "extend"}:
        update["review_due_at"] = now + timedelta(days=7)
    db.security_cases.update_one({"_id": case["_id"], "effect_pending.id": event["id"]}, {"$set": update})


def process_cases(db):
    """Durable notification/reconciliation, called by the existing Flask worker."""
    for case in db.security_cases.find({"effect_pending": {"$type": "object"}}):
        reconcile_case(db, case)
    now = utcnow()
    for case in db.security_cases.find({"status": "suspended", "review_due_at": {"$lte": now}}):
        overdue_id = f"overdue:{case['review_due_at'].isoformat()}"
        if not any(event["id"] == overdue_id for event in case["events"]):
            db.security_cases.update_one({"_id": case["_id"], "revision": case["revision"]},
                {"$inc": {"revision": 1}, "$push": {"events": {"id": overdue_id, "action": "overdue", "at": now,
                    "reason": "Seitsemän vuorokauden käsittelyaika ylittyi. Käyttöoikeus pysyy keskeytettynä.",
                    "approved": False, "actor_name": "Järjestelmä"}}})
    ids = {ObjectId(uid) for uid in board_ids(db)}
    for case in db.security_cases.find({}):
        recipients = {doc.get("email") for doc in db.users.find({"$or": [
            {"_id": {"$in": list(ids)}}, {"role": "god"},
            {"_id": ObjectId(case["target_id"])} if case["target_id"] else {"_id": None}]}) if doc.get("email")}
        for event in case["events"]:
            if not event.get("approved") and event["action"] != "overdue":
                continue
            for email in recipients:
                key = hashlib.sha256(f"{case['_id']}:{event['id']}:{email.casefold()}".encode()).hexdigest()
                if db.security_notifications.find_one({"_id": key}):
                    continue
                body = (f"Turvatapaus {case['_id']}: {case['target_name']}\nToiminto: {event['action']}\n"
                        f"Tekijä: {event['actor_name']}\nPerustelu: {event['reason']}\n\n"
                        "Hallituksen käsittely: https://mielenosoitukset.fi/admin/governance/security\n"
                        "Asianomainen voi vastata tähän viestiin kuulemista varten. Vastaus ei ole hyväksyntä.\n"
                        "Seitsemän vuorokauden määräaika ei palauta käyttöoikeutta automaattisesti.")
                job = EmailJob("Mielenosoitukset.fi: turvapäätös tai käsittelymuistutus", [email], body=body).to_dict()
                try:
                    db.email_queue.update_one({"_id": "security:" + key}, {"$setOnInsert": job}, upsert=True)
                    db.security_notifications.insert_one({"_id": key, "case_id": case["_id"], "event_id": event["id"], "queued_at": now})
                except DuplicateKeyError:
                    pass
