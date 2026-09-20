"""
Passkey (WebAuthn) and step-up (sudo) authentication endpoints.

Endpoints live under ``/users/auth/api/v2/...``:

* ``passkeys/*`` – register, list, rename and remove passkeys.
* ``passkeys/login/*`` – password-less sign-in with a passkey.
* ``step-up/*`` – re-authenticate to regain a short-lived elevated session
  used before sensitive operations such as password changes, MFA removal and
  passkey management.

All challenges are stored server-side, bound to the browser session, single-use
and short-lived (see ``webauthn_utils``).
"""

from flask import Blueprint, jsonify, request, url_for
from flask_login import current_user, login_required, login_user
from bson import ObjectId

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.users.models import User, UserMFA
from mielenosoitukset_fi.utils import webauthn_utils as webauthn
from mielenosoitukset_fi.utils.step_up import (
    grant_elevation,
    sudo_required,
)
from mielenosoitukset_fi.utils.request_ip import get_client_ip
from mielenosoitukset_fi.users.BPs.auth import (
    _find_user_by_username,
    _normalize_post_login_target,
    log_login_attempt,
)

passkeys_bp = Blueprint("passkeys", __name__, url_prefix="/auth")


# ---------------------------------------------------------------------------
# Passkey management (sensitive → requires step-up)
# ---------------------------------------------------------------------------


@passkeys_bp.route("/api/v2/passkeys", methods=["GET"])
@login_required
def list_passkeys():
    """Return the current user's registered passkeys."""
    return jsonify({"status": "success", "passkeys": webauthn.list_passkeys(current_user._id)})


@passkeys_bp.route("/api/v2/passkeys/register/options", methods=["POST"])
@login_required
@sudo_required()
def passkey_register_options():
    """Create + return WebAuthn registration options."""
    options = webauthn.registration_options(current_user)
    return jsonify({"status": "success", "options": options})


@passkeys_bp.route("/api/v2/passkeys/register/verify", methods=["POST"])
@login_required
def passkey_register_verify():
    """Verify and store a newly created passkey."""
    data = request.get_json(silent=True) or {}
    credential = data.get("credential")
    if not credential:
        return jsonify({"status": "error", "message": "credential missing"}), 400

    verified, error = webauthn.verify_registration(credential, current_user._id)
    if error:
        return jsonify({"status": "error", "message": error}), 400

    name = data.get("name", "Authenticator")
    transports = None
    if isinstance(credential, dict):
        response_obj = credential.get("response") or {}
        transports = response_obj.get("transports")
    webauthn.store_credential(current_user._id, verified, name=name, transports=transports)
    return jsonify(
        {
            "status": "success",
            "message": "Passkey tallennettu onnistuneesti.",
            "passkeys": webauthn.list_passkeys(current_user._id),
        }
    )


@passkeys_bp.route("/api/v2/passkeys/rename", methods=["POST"])
@login_required
@sudo_required()
def passkey_rename():
    data = request.get_json(silent=True) or {}
    passkey_id = data.get("id")
    name = data.get("name")
    if not passkey_id or not name:
        return jsonify({"status": "error", "message": "id and name required"}), 400

    try:
        object_id = ObjectId(passkey_id)
    except Exception:
        return jsonify({"status": "error", "message": "Virheellinen passkey-tunniste."}), 400

    if webauthn.rename_passkey(str(object_id), current_user._id, name):
        return jsonify({"status": "success", "message": "Passkey uudelleennimetty."})
    return jsonify({"status": "error", "message": "Passkeyta ei löytynyt."}), 404


@passkeys_bp.route("/api/v2/passkeys/delete", methods=["POST"])
@login_required
@sudo_required()
def passkey_delete():
    data = request.get_json(silent=True) or {}
    passkey_id = data.get("id")
    if not passkey_id:
        return jsonify({"status": "error", "message": "id required"}), 400

    try:
        object_id = ObjectId(passkey_id)
    except Exception:
        return jsonify({"status": "error", "message": "Virheellinen passkey-tunniste."}), 400

    if webauthn.delete_passkey(str(object_id), current_user._id):
        return jsonify({"status": "success", "message": "Passkey poistettu."})
    return jsonify({"status": "error", "message": "Passkeyta ei löytynyt."}), 404


# ---------------------------------------------------------------------------
# Password-less login
# ---------------------------------------------------------------------------


@passkeys_bp.route("/api/v2/passkeys/login/options", methods=["POST"])
def passkey_login_options():
    """Build login options, optionally scoped to a typed username."""
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    user_id = None
    if username:
        user_doc = _find_user_by_username(username)
        if user_doc:
            user_id = user_doc["_id"]
    options = webauthn.authentication_options(user_id=user_id, purpose=webauthn.PURPOSE_LOGIN)
    return jsonify({"status": "success", "options": options, "username": username or None})


@passkeys_bp.route("/api/v2/passkeys/login/verify", methods=["POST"])
def passkey_login_verify():
    """Verify a passkey assertion and sign the user in."""
    data = request.get_json(silent=True) or {}
    credential = data.get("credential")
    if not credential:
        return jsonify({"status": "error", "message": "credential missing"}), 400

    record, error = webauthn.verify_authentication(
        credential, user_id=None, purpose=webauthn.PURPOSE_LOGIN
    )
    if error or not record:
        return jsonify({"status": "error", "message": error or "Tuntematon passkey."}), 403

    user_doc = _get_user_doc(record.get("user_id"))
    if not user_doc:
        return jsonify({"status": "error", "message": "Käyttäjätiliä ei löytynyt."}), 403

    user = User.from_db(user_doc)
    if not user.confirmed:
        log_login_attempt(
            user.username,
            False,
            get_client_ip(),
            user_agent=request.headers.get("User-Agent", ""),
            reason="Email not verified",
            user_id=user._id,
        )
        return jsonify({"status": "error", "message": "Vahvista sähköpostiosoitteesi ennen kirjautumista."}), 403

    login_user(user)
    session_permanent()
    log_login_attempt(
        user.username,
        True,
        get_client_ip(),
        user_agent=request.headers.get("User-Agent", ""),
        user_id=user._id,
    )

    safe_next_page = _normalize_post_login_target(data.get("next") or "")
    if user.forced_pwd_reset:
        safe_next_page = url_for("users.auth.forced_pwd_reset")
    if user.forced_identity_change:
        safe_next_page = url_for("users.auth.forced_identity_change")

    return jsonify({"status": "success", "redirect": safe_next_page})


# ---------------------------------------------------------------------------
# Step-up ("sudo") authentication
# ---------------------------------------------------------------------------


@passkeys_bp.route("/api/v2/step-up/options", methods=["POST"])
@login_required
def step_up_options():
    """Describe the authentication methods the user can step up with."""
    methods = []
    if webauthn.passkey_count(current_user._id) > 0:
        methods.append({"type": "webauthn", "preferred": True})
    methods.append(
        {
            "type": "password_totp",
            "preferred": webauthn.passkey_count(current_user._id) == 0,
            "requires_totp": _user_requires_totp(),
        }
    )
    return jsonify({"status": "success", "methods": methods})


@passkeys_bp.route("/api/v2/step-up/webauthn/options", methods=["POST"])
@login_required
def step_up_webauthn_options():
    """Create a step-up assertion for the current user's passkeys."""
    options = webauthn.authentication_options(
        user_id=current_user._id, purpose=webauthn.PURPOSE_STEP_UP
    )
    return jsonify({"status": "success", "options": options})


@passkeys_bp.route("/api/v2/step-up/webauthn/verify", methods=["POST"])
@login_required
def step_up_webauthn_verify():
    """Verify a step-up assertion and grant a short-lived elevation."""
    data = request.get_json(silent=True) or {}
    credential = data.get("credential")
    if not credential:
        return jsonify({"status": "error", "message": "credential missing"}), 400

    record, error = webauthn.verify_authentication(
        credential, user_id=current_user._id, purpose=webauthn.PURPOSE_STEP_UP
    )
    if error or not record:
        return jsonify({"status": "error", "message": error or "Tuntematon passkey."}), 403

    grant_elevation("webauthn")
    return jsonify({"status": "success", "message": "Henkilöllisyys vahvistettu."})


@passkeys_bp.route("/api/v2/step-up/password", methods=["POST"])
@login_required
def step_up_password():
    """Step up with the account password (plus TOTP when MFA is enabled)."""
    data = request.get_json(silent=True) or {}
    password = data.get("password")

    if not isinstance(password, str) or not password:
        return jsonify({"status": "error", "message": "Salasana vaaditaan."}), 400

    user_doc = _get_user_doc(current_user._id)
    user = User.from_db(user_doc) if user_doc else current_user
    if not user.check_password(password):
        return jsonify({"status": "error", "message": "Väärä salasana."}), 403

    if _user_requires_totp():
        totp_code = data.get("totp_code")
        if not isinstance(totp_code, str) or not totp_code.strip():
            return jsonify(
                {"status": "error", "message": "Syötä myös MFA-koodi.", "error": "totp_required"}
            ), 400
        if not UserMFA(user._id).verify_token(totp_code.strip()):
            return jsonify({"status": "error", "message": "Väärä MFA-koodi."}), 403

    grant_elevation("password_totp")
    return jsonify({"status": "success", "message": "Henkilöllisyys vahvistettu."})


@passkeys_bp.route("/api/v2/step-up/status", methods=["GET"])
@login_required
def step_up_status():
    """Return whether the current session is still elevated."""
    from mielenosoitukset_fi.utils.step_up import is_elevated

    return jsonify({"status": "success", "elevated": is_elevated()})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_user_doc(user_id):
    db = DatabaseManager.get_instance().get_db()
    try:
        return db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        return None


def _user_requires_totp() -> bool:
    """Whether step-up password flow must also accept a TOTP code."""
    if not current_user.mfa_enabled:
        return False
    return len(UserMFA(current_user._id).list_devices()) > 0


def session_permanent():
    """Keep authenticated sessions alive for the configured ~12h lifetime."""
    from flask import session

    session.permanent = True
    session.modified = True