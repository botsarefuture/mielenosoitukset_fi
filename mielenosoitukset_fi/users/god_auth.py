"""Ordered, server-owned authentication for god accounts.

No normal login cookie is issued by an intermediate factor. Challenges are
browser-bound, expire independently of Mongo cleanup, and advance with CAS.
The final receipt is checked again by Flask-Login on every protected request.
"""
import hashlib
import hmac
import json
import secrets
from datetime import timedelta, timezone

import pyotp
from bson import ObjectId
from flask import current_app, jsonify, request, session
from flask_login import current_user, login_user
from werkzeug.security import check_password_hash, generate_password_hash

from mielenosoitukset_fi.emailer.EmailJob import EmailJob
from mielenosoitukset_fi.utils import webauthn_utils as webauthn
from mielenosoitukset_fi.utils.request_ip import get_client_ip
from mielenosoitukset_fi.utils.system_teams import active_account, clearance_approved, olivia_user_id, user_team_access
from mielenosoitukset_fi.utils.time_utils import utcnow

PENDING_KEY = "god_pending"
RECEIPT_KEY = "god_login_receipt"
CSRF_KEY = "god_csrf"
SETUP_KEY = "god_setup"
TTL = timedelta(minutes=15)
SESSION_TTL = timedelta(minutes=30)
STAGES = ("totp_first", "email_code", "passkey", "totp_second", "email_link", "final_secret", "complete")


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _mac(value):
    return hmac.new(str(current_app.secret_key).encode(), value.encode(), hashlib.sha256).hexdigest()


def _factors(db, user):
    ids = (user.get("god_security") or {}).get("totp_ids") or []
    if len(ids) != 2 or len(set(map(str, ids))) != 2 or not all(ObjectId.is_valid(str(value)) for value in ids):
        return []
    rows = [db.mfas.find_one({"_id": ObjectId(value), "user_id": user["_id"]}) for value in ids]
    if not all(row and row.get("secret") for row in rows) or rows[0]["secret"] == rows[1]["secret"]:
        return []
    return rows


def credential_version(db, user):
    factors = _factors(db, user)
    keys = list(db.user_passkeys.find({"user_id": user["_id"]}, {"credential_id": 1, "public_key": 1}))
    security = user.get("god_security") or {}
    if len(factors) != 2 or not keys or not security.get("secret_hash") or security.get("policy") != 1:
        return None
    material = [user.get("password_hash"), user.get("email"), security["secret_hash"],
                [(str(row["_id"]), row["secret"]) for row in factors],
                sorted((row["credential_id"], row["public_key"]) for row in keys)]
    return digest(json.dumps(material, separators=(",", ":")))


def eligible(db, user):
    return bool(user and user.get("role") == "god" and active_account(user)
                and clearance_approved(db, user["_id"]) and "national" in user_team_access(db, user["_id"]))


def valid_god_session(db, user, maximum_age=None):
    token = session.get(RECEIPT_KEY)
    if not isinstance(token, str) or not eligible(db, user):
        return False
    proof = db.mfa_login_challenges.find_one({"_id": digest(token), "kind": "god_login", "stage": "complete",
                                            "user_id": user["_id"], "expires_at": {"$gt": utcnow()}})
    return bool(proof and proof.get("version") == credential_version(db, user)
                and (maximum_age is None or proof["completed_at"] > utcnow() - timedelta(seconds=maximum_age)))


def _queue_mail(db, user, body):
    # Use the existing Flask delivery worker, but acknowledge durable enqueue
    # instead of the legacy queue helper's silent, hour-delayed insert retries.
    job = EmailJob("God-tilin kirjautumisen vahvistus", [user["email"]], body=body)
    db.email_queue.insert_one(job.to_dict())


def _rate_limit(db, identity):
    bucket = int(utcnow().timestamp()) // 900
    key = "god-limit:" + _mac(f"{identity}:{bucket}")
    row = db.mfa_login_challenges.find_one_and_update({"_id": key}, {
        "$inc": {"attempts": 1}, "$setOnInsert": {"kind": "god_rate_limit", "expires_at": utcnow() + TTL * 2}}, upsert=True)
    if row and row.get("attempts", 0) >= 10:
        raise PermissionError("Liian monta yritystä. Yritä myöhemmin uudelleen.")


def start_login(db, username, password):
    _rate_limit(db, "ip:" + str(get_client_ip()))
    _rate_limit(db, "user:" + str(username).casefold())
    user = db.users.find_one({"username_canonical": str(username).strip().casefold()})
    if not user:
        user = db.users.find_one({"username": str(username).strip()})
    if not isinstance(password, str) or not 32 <= len(password) <= 4096 or not eligible(db, user):
        raise PermissionError("Kirjautuminen ei onnistunut.")
    if not check_password_hash(user["password_hash"], password):
        raise PermissionError("Kirjautuminen ei onnistunut.")
    version = credential_version(db, user)
    if not version:
        raise PermissionError("Tilin turvatekijöiden käyttöönotto on kesken.")
    old = session.pop(PENDING_KEY, None)
    if old:
        db.mfa_login_challenges.delete_one({"_id": digest(old), "kind": "god_login"})
    token = secrets.token_urlsafe(32)
    db.mfa_login_challenges.insert_one({"_id": digest(token), "kind": "god_login", "user_id": user["_id"],
        "stage": "totp_first", "revision": 0, "attempts": 0, "version": version, "expires_at": utcnow() + TTL})
    session[PENDING_KEY] = token
    return {"stage": "totp_first"}


def _pending(db):
    token = session.get(PENDING_KEY)
    proof = db.mfa_login_challenges.find_one({"_id": digest(token), "kind": "god_login", "stage": {"$ne": "complete"},
        "expires_at": {"$gt": utcnow()}, "attempts": {"$lt": 5}}) if isinstance(token, str) else None
    user = db.users.find_one({"_id": proof["user_id"]}) if proof else None
    if not proof or not eligible(db, user) or proof.get("version") != credential_version(db, user):
        raise PermissionError("Kirjautumisvahvistus on vanhentunut. Aloita uudelleen.")
    return proof, user


def _advance(db, proof, stage, **fields):
    changed = db.mfa_login_challenges.update_one({"_id": proof["_id"], "revision": proof["revision"],
        "stage": proof["stage"], "expires_at": {"$gt": utcnow()}, "attempts": {"$lt": 5}},
        {"$set": {"stage": stage, "attempts": 0, **fields}, "$inc": {"revision": 1}})
    if not changed.matched_count:
        raise PermissionError("Vahvistus on jo käytetty. Päivitä näkymä.")
    return {"stage": stage}


def _consume_totp(db, factor, code):
    if not isinstance(code, str) or len(code) != 6 or not code.isascii() or not code.isdigit():
        return False
    counter = int(utcnow().replace(tzinfo=timezone.utc).timestamp()) // 30
    totp = pyotp.TOTP(factor["secret"])
    for value in (counter, counter - 1, counter + 1):
        if hmac.compare_digest(totp.generate_otp(value), code):
            result = db.mfas.update_one({"_id": factor["_id"], "$or": [
                {"god_last_counter": {"$exists": False}}, {"god_last_counter": {"$lt": value}}]},
                {"$set": {"god_last_counter": value}})
            return result.matched_count == 1
    return False


def _fail(db, proof):
    db.mfa_login_challenges.update_one({"_id": proof["_id"], "revision": proof["revision"]}, {"$inc": {"attempts": 1}})
    raise PermissionError("Vahvistus ei onnistunut.")


def _origin():
    return current_app.config.get("GOD_AUTH_ORIGIN", "https://mielenosoitukset.fi").rstrip("/")


def _allowed_origins():
    origin = _origin()
    return {origin, "https://www.mielenosoitukset.fi"} if origin == "https://mielenosoitukset.fi" else {origin}


def _email_origin():
    # Keep browser-bound links on the same approved hostname as the initiating
    # session. Never derive an authentication URL from an arbitrary Host header.
    origin = request.headers.get("Origin")
    return origin if origin in _allowed_origins() else _origin()


def activate_enrolled_candidate(db, user_id):
    """Either ordering of owner enrollment and board consent is supported."""
    user = db.users.find_one({"_id": ObjectId(str(user_id)), "god_candidate": True, "god_security.policy": 1})
    from mielenosoitukset_fi.utils.god_appointments import appointment_approved
    if (not user or not credential_version(db, user) or not appointment_approved(db, user_id)
            or not clearance_approved(db, user_id) or "national" not in user_team_access(db, user_id)):
        return False
    changed = db.users.update_one({"_id": user["_id"], "god_candidate": True, "god_security.policy": 1}, {"$set": {
        "role": "god", "active": True, "confirmed": True, "governance_managed": True, "god_candidate": False}})
    if changed.modified_count:
        db.api_tokens.delete_many({"user_id": user["_id"]})
        db.board_audit_logs.insert_one({"user_id": str(user_id), "action": "god-tilin aktivointi",
            "timestamp": utcnow(), "owner_id": olivia_user_id()})
    return bool(changed.matched_count)


def _setup_pending(db):
    if not current_user.is_authenticated or not current_user.confirmed or str(current_user.id) != olivia_user_id() or current_user.role == "god":
        raise PermissionError("Käyttöönotto vaatii Olivian tavallisen käyttäjätilin.")
    handle = session.get(SETUP_KEY)
    proof = db.mfa_login_challenges.find_one({"_id": digest(handle), "kind": "god_enrollment", "owner_id": str(current_user.id),
        "expires_at": {"$gt": utcnow()}, "attempts": {"$lt": 5}, "stage": {"$ne": "complete"}}) if isinstance(handle, str) else None
    user = db.users.find_one({"_id": proof["user_id"], "god_candidate": True, "active": False,
                              "god_security.policy": {"$ne": 1}}) if proof else None
    if not user or proof.get("owner_version") != digest(current_user.password_hash):
        raise PermissionError("Käyttöönotto on vanhentunut. Aloita uudelleen.")
    return proof, user


def _setup_status(db):
    proof, user = _setup_pending(db)
    result = {"stage": proof["stage"]}
    if proof["stage"] == "enroll_passkey":
        result["authenticators"] = [pyotp.TOTP(value).provisioning_uri(name=f"{user['username']} ({index + 1})",
                                   issuer_name="Mielenosoitukset.fi") for index, value in enumerate(proof["totp_secrets"])]
    return result


def _enroll_action(db, action, data):
    if action == "enroll_start":
        if not current_user.is_authenticated or not current_user.confirmed or str(current_user.id) != olivia_user_id() or current_user.role == "god":
            raise PermissionError("Kirjaudu ensin Olivian tavalliselle käyttäjätilille.")
        _rate_limit(db, "setup:" + str(current_user.id))
        from mielenosoitukset_fi.users.models import UserMFA
        if not current_user.check_password(data.get("password") or "") or not UserMFA(current_user._id).verify_token(str(data.get("code") or "")):
            raise PermissionError("Vahvista tavallisen tilin salasana ja authenticator-koodi.")
        user = db.users.find_one({"username_canonical": "godolivia", "god_candidate": True, "active": False,
                                  "god_security.policy": {"$ne": 1}})
        if not user:
            raise PermissionError("Käyttöönottoa odottavaa tiliä ei löytynyt.")
        old = session.pop(SETUP_KEY, None)
        if old:
            db.mfa_login_challenges.delete_one({"_id": digest(old), "kind": "god_enrollment"})
        handle, email_token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        db.mfa_login_challenges.insert_one({"_id": digest(handle), "kind": "god_enrollment", "user_id": user["_id"],
            "owner_id": str(current_user.id), "owner_version": digest(current_user.password_hash), "stage": "enroll_email",
            "revision": 0, "attempts": 0, "email_token": digest(email_token), "expires_at": utcnow() + TTL})
        session[SETUP_KEY] = handle
        _queue_mail(db, user, f"Vahvista god-tilin käyttöönotto samassa selaimessa:\n{_email_origin()}/auth/god#enroll={email_token}\nÄlä jaa linkkiä.")
        return {"stage": "enroll_email"}
    proof, user = _setup_pending(db)
    if action == "enroll_email" and proof["stage"] == "enroll_email":
        if not isinstance(data.get("token"), str) or not hmac.compare_digest(proof["email_token"], digest(data["token"])):
            _fail(db, proof)
        _advance(db, proof, "enroll_passkey", email_token=None, totp_secrets=[pyotp.random_base32(), pyotp.random_base32()],
                 totp_ids=[ObjectId(), ObjectId()])
        return _setup_status(db)
    if action == "enroll_passkey_options" and proof["stage"] == "enroll_passkey":
        from mielenosoitukset_fi.users.models import User
        return {"stage": proof["stage"], "options": webauthn.registration_options(User.from_db(user), require_user_verification=True)}
    if action == "enroll_passkey_verify" and proof["stage"] == "enroll_passkey":
        verified, error = webauthn.verify_registration(data.get("credential"), user["_id"], require_user_verification=True)
        if error or not verified:
            _fail(db, proof)
        webauthn.store_credential(user["_id"], verified, name="God-kirjautuminen")
        return _advance(db, proof, "enroll_secrets")
    if action == "enroll_secrets" and proof["stage"] == "enroll_secrets":
        password, secret = data.get("password"), data.get("secret")
        if (not isinstance(password, str) or not 32 <= len(password) <= 4096 or not isinstance(secret, str)
                or not 64 <= len(secret) <= 4096 or password == secret):
            raise PermissionError("Anna eri salasanat: vähintään 32 ja 64 merkkiä.")
        codes = data.get("codes")
        if not isinstance(codes, list) or len(codes) != 2 or any(not isinstance(code, str) or not pyotp.TOTP(value).verify(code, valid_window=1)
                                                  for value, code in zip(proof["totp_secrets"], codes)):
            _fail(db, proof)
        # Only this initial, owner-bound enrollment can install the policy.
        # Persist hashed secrets before consuming, so a transient write failure
        # can be retried without leaving an activated, partially enrolled user.
        for oid, value in zip(proof["totp_ids"], proof["totp_secrets"]):
            db.mfas.update_one({"_id": oid}, {"$setOnInsert": {"user_id": user["_id"], "secret": value,
                "device_name": "God authenticator", "created_at": utcnow()}}, upsert=True)
        changed = db.users.update_one({"_id": user["_id"], "god_candidate": True, "active": False, "god_security.policy": {"$ne": 1}},
            {"$set": {"password_hash": generate_password_hash(password), "mfa_enabled": True,
                "god_security": {"policy": 1, "secret_hash": generate_password_hash(secret), "totp_ids": proof["totp_ids"],
                                 "enrolled_at": utcnow(), "owner_id": str(current_user.id)}}})
        if not changed.matched_count:
            raise PermissionError("Käyttöönotto on jo tehty.")
        _advance(db, proof, "complete", totp_secrets=None, email_token=None)
        session.pop(SETUP_KEY, None)
        activated = activate_enrolled_candidate(db, user["_id"])
        return {"stage": "enrolled", "activated": activated}
    raise PermissionError("Suorita käyttöönoton vaiheet järjestyksessä.")


def handle_action(db, data):
    """Dispatch JSON actions through the existing account login endpoint."""
    if not isinstance(data, dict):
        return jsonify(message="Virheellinen pyyntö."), 400
    if request.headers.get("Origin") not in _allowed_origins():
        return jsonify(message="Istunnon turvatarkistus epäonnistui."), 403
    action = data.get("god_action")
    if action == "status":
        csrf = session.setdefault(CSRF_KEY, secrets.token_urlsafe(32))
        try:
            proof, _ = _pending(db)
            stage = proof["stage"]
        except PermissionError:
            stage = "start"
        if stage == "start" and session.get(SETUP_KEY):
            try:
                return jsonify(**_setup_status(db), csrf=csrf)
            except PermissionError:
                pass
        return jsonify(stage=stage, csrf=csrf)
    expected = session.get(CSRF_KEY)
    if not expected or not hmac.compare_digest(expected, str(request.headers.get("X-CSRF-Token", ""))):
        return jsonify(message="Istunnon turvatarkistus epäonnistui."), 403
    try:
        if isinstance(action, str) and action.startswith("enroll_"):
            return jsonify(_enroll_action(db, action, data))
        if action == "start":
            return jsonify(start_login(db, data.get("username"), data.get("password")))
        proof, user = _pending(db)
        stage = proof["stage"]
        if action == "passkey_options" and stage == "passkey":
            return jsonify(stage=stage, options=webauthn.authentication_options(user["_id"], purpose="god_login", require_user_verification=True))
        if action != stage:
            raise PermissionError("Suorita kirjautumisen vaiheet järjestyksessä.")
        if stage in {"totp_first", "totp_second"}:
            factor = _factors(db, user)[0 if stage == "totp_first" else 1]
            if not _consume_totp(db, factor, data.get("code")):
                _fail(db, proof)
            if stage == "totp_first":
                code = f"{secrets.randbelow(1000000):06d}"
                result = _advance(db, proof, "email_code", email_code=_mac(proof["_id"] + code))
                _queue_mail(db, user, f"Kirjautumisen vahvistuskoodi: {code}\nVoimassa 15 minuuttia kirjautumisen alusta. Jos et kirjautunut, älä käytä koodia.")
                return jsonify(result)
            token = secrets.token_urlsafe(32)
            result = _advance(db, proof, "email_link", email_token=digest(token))
            _queue_mail(db, user, f"Vahvista aloittamasi kirjautuminen:\n{_email_origin()}/auth/god#verify={token}\nAvaa linkki samassa selaimessa. Pelkkä linkin avaaminen ei kirjaa sisään.")
            return jsonify(result)
        if stage == "email_code":
            code = data.get("code")
            if not isinstance(code, str) or not hmac.compare_digest(proof.get("email_code", ""), _mac(proof["_id"] + code)):
                _fail(db, proof)
            return jsonify(_advance(db, proof, "passkey"))
        if stage == "passkey":
            key, error = webauthn.verify_authentication(data.get("credential"), user["_id"], purpose="god_login", require_user_verification=True)
            if error or not key:
                _fail(db, proof)
            return jsonify(_advance(db, proof, "totp_second"))
        if stage == "email_link":
            token = data.get("token")
            if not isinstance(token, str) or not hmac.compare_digest(proof.get("email_token", ""), digest(token)):
                _fail(db, proof)
            return jsonify(_advance(db, proof, "final_secret", email_token=None))
        if stage == "final_secret":
            secret = data.get("secret")
            if not isinstance(secret, str) or not 64 <= len(secret) <= 4096 or not check_password_hash(user["god_security"]["secret_hash"], secret):
                _fail(db, proof)
            # Re-read policy and credentials before committing the final receipt.
            fresh = db.users.find_one({"_id": user["_id"]})
            if not eligible(db, fresh) or credential_version(db, fresh) != proof["version"]:
                _fail(db, proof)
            _advance(db, proof, "complete", completed_at=utcnow(), expires_at=utcnow() + SESSION_TTL)
            from mielenosoitukset_fi.users.models import User
            login_user(User.from_db(fresh), remember=False, fresh=True)
            session[RECEIPT_KEY] = session.pop(PENDING_KEY)
            session.permanent = True
            db.board_audit_logs.insert_one({"user_id": str(user["_id"]), "action": "god-kirjautuminen",
                "proof_id": proof["_id"], "timestamp": utcnow()})
            return jsonify(stage="complete", redirect="/admin/governance/")
        raise PermissionError("Virheellinen kirjautumisvaihe.")
    except PermissionError as exc:
        return jsonify(message=str(exc)), 403
