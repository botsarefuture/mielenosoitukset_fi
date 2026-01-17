import json
from flask import (
    Blueprint,
    g,
    render_template,
    request,
    redirect,
    url_for,
    current_app,
    session,
)
from urllib.parse import urlparse
from flask_login import login_user, logout_user, login_required, current_user
from mielenosoitukset_fi.users.models import MFAToken, PendingMFA, User, UserMFA
from mielenosoitukset_fi.utils.auth import (
    generate_confirmation_token,
    verify_confirmation_token,
    generate_reset_token,
    verify_reset_token,
)
from mielenosoitukset_fi.utils.flashing import flash_message
from mielenosoitukset_fi.utils.helpers import is_strong_password
from mielenosoitukset_fi.utils.s3 import upload_image, upload_image_fileobj
from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.classes import Organization
from bson.objectid import ObjectId
from werkzeug.utils import secure_filename
import importlib
import os
import jwt
import datetime

# import stuff needed for qr code generation
import pyqrcode
import base64
from io import BytesIO
from flask import jsonify

from mielenosoitukset_fi.utils.tokens import TOKEN_USAGE_LOGS, TOKENS_COLLECTION, create_token


def generate_qr(url: str) -> str:
    """
    Generate a QR code for the given URL and return it as a base64-encoded string.

    Parameters
    ----------
    url : str
        The URL to encode in the QR code.

    Returns
    -------
    str
        The base64-encoded string representation of the QR code image.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError("Invalid URL. The URL must be a non-empty string.")

    qr = pyqrcode.create(url)  # Generate the QR code
    buffer = BytesIO()  # Create an in-memory bytes buffer
    qr.png(buffer, scale=6)  # Save the QR code as a PNG into the buffer
    buffer.seek(0)  # Reset the buffer's position to the beginning
    img_base64 = base64.b64encode(buffer.read()).decode(
        "utf-8"
    )  # Convert image bytes to base64
    return img_base64


EmailSender = importlib.import_module(
    "mielenosoitukset_fi.emailer.EmailSender", "mielenosoitukset_fi"
).EmailSender

email_sender = EmailSender()
db_manager = DatabaseManager().get_instance()
mongo = db_manager.get_db()

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


login_logs = mongo["login_logs"]

from datetime import datetime

def log_login_attempt(username, success, ip, user_agent=None, reason=None, user_id=None):
    """
    Logs a login attempt to MongoDB.

    Parameters
    ----------
    username : str
    success : bool
    ip : str
    user_agent : str, optional
    reason : str, optional
    user_id : ObjectId, optional
    """
    # If login was successful, update the user's last login
    if success:
        try:
            user_query = {"username": username}
            if user_id:
                user_query["_id"] = ObjectId(user_id)
            user = mongo.users.find_one(user_query)
            if user:
                mongo.users.update_one(
                    {"_id": ObjectId(user["_id"])},
                    {"$set": {"last_login": datetime.utcnow()}}
                )
                
        except Exception as e:
            # Optional: log the exception somewhere
            print(f"Failed to update last login: {e}")
            
    login_logs.insert_one({
        "username": username,
        "user_id": ObjectId(user_id) if user_id else None,
        "success": success,
        "ip": ip,
        "user_agent": user_agent,
        "reason": reason,
        "timestamp": datetime.utcnow(),
    })


def verify_emailer(email, username):
    """

    Parameters
    ----------
    email :
        param username:
    username :


    Returns
    -------


    """
    token = generate_confirmation_token(email)
    confirmation_url = url_for("users.auth.confirm_email", token=token, _external=True)
    email_sender.queue_email(
        template_name="registration_confirmation_email.html",
        subject="Vahvista rekisteröitymisesi",
        recipients=[email],
        context={"confirmation_url": confirmation_url, "user_name": username},
    )


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """ """
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        email = request.form.get("email")

        if not username or not password or len(username) < 3 or not is_strong_password(password):
            flash_message(
                "Virheellinen syöte. Käyttäjänimen tulee olla vähintään 3 merkkiä pitkä ja salasanan vähintään 6 merkkiä pitkä.",
                "error",
            )
            return redirect(url_for("users.auth.register"))

        if mongo.users.find_one({"username": username}):
            flash_message("Käyttäjänimi on jo käytössä.", "warning")
            return redirect(url_for("users.auth.register"))

        if mongo.users.find_one({"email": email}):
            flash_message(
                "Sähköpostiosoite on jo rekisteröity. Kirjaudu sisään sen sijaan.",
                "warning",
            )
            return redirect(url_for("users.auth.login"))

        user_data = User.create_user(username, password, email)
        mongo.users.insert_one(user_data)

        try:
            verify_emailer(email, username)
            flash_message(
                "Rekisteröinti onnistui! Tarkista sähköpostisi vahvistaaksesi tilisi.",
                "info",
            )
        except Exception as e:
            flash_message(f"Virhe vahvistusviestin lähettämisessä: {e}", "error")

        # lets add the email to the session for next steps
        g.email = email 
        return redirect(url_for("users.auth.register_next_steps"))
        return redirect(url_for("users.auth.login"))

    return render_template("users/auth/register.html")


@auth_bp.route("/register/next_steps")
def register_next_steps():
        
    return render_template("users/auth/register_next_steps.html", email=g.get("email", 'Tapahtui virhe ja emme löydä sähköpostiasi.'), email_found=bool(g.get("email", None)))


# ------------------------
# Generate a new API token
# ------------------------
@auth_bp.route("/api_token", methods=["POST"])
@login_required
def generate_api_token():
    data = request.get_json() or {}
    token_type = data.get("type", "short")
    scopes = data.get("scopes", ["read"])

    # Admin scope check
    if "admin" in scopes and not (current_user.global_admin or current_user.role in ["admin", "superuser"]):
        scopes.remove("admin")
        TOKEN_USAGE_LOGS.insert_one({
            "user_id": current_user._id,
            "username": current_user.username,
            "action": "attempted admin scope request",
            "requested_scopes": data.get("scopes", []),
            "allowed_scopes": scopes,
            "ip_address": request.remote_addr,
            "timestamp": datetime.now()
        })

    try:
        token, expires_at = create_token(user_id=current_user._id, token_type=token_type, scopes=scopes)
        return jsonify({
            "status": "success",
            "token": token,          # raw token (showed only once)
            "expires_at": expires_at.isoformat(),
            "scopes": scopes,
            "type": token_type
        })
    except ValueError as e:
        return jsonify({"status": "error", "error": str(e)}), 400
    

# ------------------------
# List all tokens for user
# ------------------------
@auth_bp.route("/api_tokens/list")
@login_required
def list_tokens():
    tokens = list(TOKENS_COLLECTION.find({"user_id": current_user._id}))
    # We never send hashed token back
    token_list = []
    for t in tokens:
        token_list.append({
            "_id": str(t["_id"]),
            "type": t["type"],
            "scopes": t.get("scopes", []),
            "expires_at": t.get("expires_at").isoformat() if t.get("expires_at") else None,
        })
    return jsonify({"status": "success", "tokens": token_list})

# ------------------------
# Revoke a token
# ------------------------
@auth_bp.route("/api_tokens/revoke", methods=["POST"])
@login_required
def revoke_token():
    data = request.get_json() or {}
    token_id = data.get("token_id")
    if not token_id:
        return jsonify({"status": "error", "message": "token_id required"}), 400

    result = TOKENS_COLLECTION.delete_one({"_id": ObjectId(token_id), "user_id": current_user._id})
    if result.deleted_count == 1:
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Token not found"}), 404

@auth_bp.route("/ui/tokens")
def tokens_ui():
    return render_template("users/auth/token_ui.html")

@auth_bp.route("/api/username_free", methods=["GET"])
def api_username_free():
    username = request.args.get("username", "").strip()
    if not username:
        return jsonify({"available": False, "error": "Username is required."}), 400

    is_taken = mongo.users.find_one({"username": username}) is not None
    return jsonify({"available": not is_taken})

@auth_bp.route("/confirm_email/<token>")
def confirm_email(token):
    """

    Parameters
    ----------
    token :


    Returns
    -------


    """
    email = verify_confirmation_token(token)
    if email:
        user = mongo.users.find_one({"email": email})
        if user:
            mongo.users.update_one({"email": email}, {"$set": {"confirmed": True}})
            flash_message(
                "Sähköpostiosoitteesi on vahvistettu. Voit nyt kirjautua sisään.",
                "info",
            )
        else:
            flash_message("Käyttäjää ei löytynyt.", "error")
    else:
        flash_message("Vahvistuslinkki on virheellinen tai vanhentunut.", "warning")

    return redirect(url_for("users.auth.login"))


@auth_bp.route("/resend_confirmation", methods=["POST"])
def resend_confirmation():
    email_or_username = (request.form.get("email_or_username") or "").strip()
    
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        # AJAX request
        if not email_or_username:
            return jsonify({"status": "error", "message": "Syötä sähköposti tai käyttäjänimi."}), 400

        lookup_values = [email_or_username]
        if "@" in email_or_username:
            lookup_values.append(email_or_username.lower())

        user_doc = mongo.users.find_one({
            "$or": [{"email": {"$in": lookup_values}}, {"username": email_or_username}]
        })

        if user_doc:
            user = User.from_db(user_doc)
            if not user.confirmed:
                try:
                    verify_emailer(user.email, user.username)
                except Exception as e:
                    return jsonify({"status": "error", "message": f"Vahvistusviestin lähetys epäonnistui: {e}"}), 500

        return jsonify({
            "status": "success",
            "message": "Jos tili on olemassa ja sähköposti on vahvistamatta, lähetimme uuden vahvistuslinkin."
        })
    # Non-AJAX request
    if not email_or_username:
        flash_message("Syötä sähköposti tai käyttäjänimi.", "warning")
        return redirect(url_for("users.auth.login"))

    lookup_values = [email_or_username]
    if "@" in email_or_username:
        lookup_values.append(email_or_username.lower())

    user_doc = mongo.users.find_one({
        "$or": [{"email": {"$in": lookup_values}}, {"username": email_or_username}]
    })

    if user_doc:
        user = User.from_db(user_doc)
        if not user.confirmed:
            try:
                verify_emailer(user.email, user.username)
            except Exception as e:
                flash_message(f"Vahvistusviestin lähetys epäonnistui: {e}", "error")
                return redirect(url_for("users.auth.login"))

    flash_message(
        "Jos tili on olemassa ja sähköposti on vahvistamatta, lähetimme uuden vahvistuslinkin.",
        "info",
    )
    return redirect(url_for("users.auth.login"))


@auth_bp.route("/check_email_verified", methods=["POST"])
def check_email_verified():
    """
    Check if the user's email is verified.

    Returns
    -------
    dict
        A dictionary indicating whether the email is verified.
    """
    try:
        user = mongo.users.find_one({"email": request.json.get("email")})
        user = User.from_db(user)
        return jsonify({"verified": user.confirmed})
    except Exception as e:
        return jsonify({"verified": False})

@auth_bp.route("/2fa_check", methods=["POST"])
def mfa_check():
    """
    Check if the user has MFA enabled and if the provided credentials are valid.

    Returns
    -------
    dict
        A dictionary containing the MFA status and validity of the credentials.
    """

    try:
        user = mongo.users.find_one({"username": request.form.get("username")})
        user = User.from_db(user)
        if not user.check_password(request.form.get("password")):
            return jsonify({"enabled": False, "valid": False})

        if not user.confirmed:
            try:
                verify_emailer(user.email, user.username)
            except Exception:
                pass
            return jsonify({"enabled": False, "valid": False, "unverified": True})

        return jsonify({"enabled": user.mfa_enabled, "valid": True})

    except Exception as e:
        return jsonify({"enabled": False, "valid": False})

from urllib.parse import urlparse

def _check(safe_next_page, request):
    
    # Check if this is a popup login request
    if request.args.get("popup") == "1":
        # Return HTML that closes the popup and reloads opener
        return f"""
        <script>
            if (window.opener) {{
                window.opener.location.reload();
                window.close();
            }} else {{
                window.location = "{safe_next_page}";
            }}
        </script>
        """, True
    
    else:
        return None, False

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # Get the next page from GET param or from session fallback
    next_page = request.args.get("next") or session.get("next_page") or ""

    # Sanitize next_page: remove backslashes etc.
    next_page = next_page.replace("\\", "")

    # Check if next_page is a safe internal URL (no netloc, no scheme)
    if next_page and (urlparse(next_page).netloc == "" and urlparse(next_page).scheme == ""):
        safe_next_page = next_page
    else:
        # fallback default redirect page after login
        safe_next_page = url_for("index")

    # Prevent redirect back to login page itself to avoid loops
    if safe_next_page == url_for("users.auth.login"):
        safe_next_page = url_for("index")

    # Save the safe next page to session in case of POST failures
    session["next_page"] = safe_next_page
    session.modified = True
    
    if current_user.is_authenticated:
        return redirect(safe_next_page)

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            flash_message("Anna sekä käyttäjänimi että salasana.", "warning")
            return redirect(url_for("users.auth.login", next=safe_next_page))

        user_doc = mongo.users.find_one({"username": username})
        
        user_ip = request.remote_addr
        user_agent = request.headers.get("User-Agent", "")

        if not user_doc:
            flash_message(f"Käyttäjänimellä '{username}' ei löytynyt käyttäjiä.", "error")
            log_login_attempt(username, False, user_ip, user_agent=user_agent, reason="User not found")
            return redirect(url_for("users.auth.login", next=safe_next_page))

        user = User.from_db(user_doc)
        if not user.check_password(password):
            flash_message("Käyttäjänimi tai salasana on väärin.", "error")
            log_login_attempt(username, False, user_ip, user_agent=user_agent, reason="Invalid password", user_id=user.id)
            return redirect(url_for("users.auth.login", next=safe_next_page))

        if not user.confirmed:
            flash_message(
                "Kirjautuminen estetty: vahvista sähköpostiosoitteesi ennen kirjautumista. "
                "Tarkista sähköpostisi ja avaa vahvistuslinkki (lähetimme uuden linkin).",
                "warning",
            )
            verify_emailer(user.email, username)
            log_login_attempt(username, False, user_ip, user_agent=user_agent, reason="Email not verified", user_id=user.id)
            return redirect(url_for("users.auth.login", next=safe_next_page))

        # MFA check (assuming your meow function does this)
        if user.mfa_enabled and not meow(user):
            log_login_attempt(username, success=False, ip=user_ip, user_agent=user_agent, reason="MFA failed", user_id=user._id)
            return redirect(url_for("users.auth.login", next=safe_next_page))


        # Everything good, log the user in
        login_user(user)
        log_login_attempt(username, success=True, ip=user_ip, user_agent=user_agent, user_id=user._id)

        if user.forced_pwd_reset:
            # somehow lets keep the redirect page
            session["next_page"] = safe_next_page
            return redirect(url_for("users.auth.forced_pwd_reset"))

        # Clear the stored next_page so it won't persist forever
        if "next_page" in session:
            session.pop("next_page")
            session.modified = True

        __, b = _check(safe_next_page, request)
        if b:
            return __, 200

        if safe_next_page == url_for("users.profile.api_friends_list"):
            safe_next_page = url_for("users.profile.profile")

        # Redirect to the safe next page
        return redirect(safe_next_page)

    # GET request just renders login page
    return render_template("users/auth/login.html", next=safe_next_page)
from datetime import datetime

@auth_bp.route("/forced_pwd_reset/", methods=["GET", "POST"])
@login_required
def forced_pwd_reset():
    ip = request.remote_addr
    user_agent = request.headers.get("User-Agent", "")

    log_entry = {
        "user_id": str(current_user.id),
        "datetime": datetime.utcnow(),
        "ip": ip,
        "user_agent": user_agent,
        "visit": True,
        "changed": False,
        "error": None,
        "method": "forced_reset"
    }

    if request.method == "POST":
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if not new_password or not confirm_password:
            log_entry["error"] = "Password or confirmation missing"
            mongo.password_changes.insert_one(log_entry)
            flash_message("Anna uusi salasana ja vahvista se.", "warning")
            return redirect(url_for("users.auth.forced_pwd_reset"))

        if new_password != confirm_password:
            log_entry["error"] = "Passwords do not match"
            mongo.password_changes.insert_one(log_entry)
            flash_message("Salasanat eivät täsmää.", "error")
            return redirect(url_for("users.auth.forced_pwd_reset"))

        if not is_strong_password(new_password, username=current_user.username, email=current_user.email):
            log_entry["error"] = "Password does not meet requirements"
            mongo.password_changes.insert_one(log_entry)
            flash_message("Salasana ei täytä vaatimuksia.", "warning")
            return redirect(url_for("users.auth.forced_pwd_reset"))

        try:
            current_user._change_password(new_password)
            log_entry["changed"] = True
            current_user.forced_pwd_reset = False
            current_user.save()
            mongo.password_changes.insert_one(log_entry)
            flash_message("Salasana on vaihdettu onnistuneesti.", "success")
        except Exception as e:
            log_entry["error"] = f"Password change failed: {e}"
            mongo.password_changes.insert_one(log_entry)
            flash_message(f"Salasanan vaihto epäonnistui: {e}", "error")
            return redirect(url_for("users.auth.forced_pwd_reset"))

        # ✅ Get safe next page from session, fallback to profile
        safe_next_page = session.pop("next_page", None) or url_for("users.profile.profile")
        
        # Optional: double-check _check()
        __, b = _check(safe_next_page, request)
        if b:
            return __, 200

        if safe_next_page == url_for("users.profile.api_friends_list"):
            safe_next_page = url_for("users.profile.profile")

        return redirect(safe_next_page)

    # log GET visit
    mongo.password_changes.insert_one(log_entry)
    return render_template("users/auth/forced_pwd_reset.html")



def meow(user):
    token = request.form.get("2fa_code")
    if not token:
        flash_message("Anna MFA-koodi.", "warning")
        return False

    if not UserMFA(user._id).verify_token(token):
        flash_message("Väärä MFA-koodi.", "error")
        return False

    return True


@auth_bp.route("/verify_mfa", methods=["GET", "POST"])
def verify_mfa():
    """ """
    if not session.get("mfa_required"):
        return redirect(url_for("users.auth.login"))

    if request.method == "POST":
        token = request.form.get("token")
        next = request.args.get("next")
        user = current_user

        if UserMFA(user._id).verify_mfa(token):
            
            login_user(user)
            
            
            session["mfa_required"] = False
            session["modified"] = True
            
            # Check if this is a popup login request
            if request.args.get("popup") == "1":
                # Return HTML that closes the popup and reloads opener
                return f"""
                <script>
                    if (window.opener) {{
                        window.opener.location.reload();
                        window.close();
                    }} else {{
                        window.location = "{safe_next_page}";
                    }}
                </script>
                """

            if user.forced_pwd_reset:
                return redirect(url_for("users.auth.forced_pwd_reset"))

            return redirect(next or url_for("index"))

        flash_message("Väärä MFA-koodi", "error")
        return redirect(url_for("users.auth.verify_mfa"))

    return render_template("users/auth/verify_mfa.html")

@auth_bp.route("/api/v1/settings/", methods=["POST"])
@login_required
def settings_api():
    """
    Update settings for the current user by comparing the provided data with the existing data.
    For any field that differs, update the database, send an email notification, and start a process.
    
    This now includes additional settings such as language, dark_mode, and city selections.

    Parameters
    ----------
    None

    Returns
    -------
    flask.Response
        A JSON response indicating whether settings were updated.
    """
    user = current_user
    user_data = request.form.to_dict()
    changed_fields = {}

    # Build current_user_data from attributes (use underscore field names)
    current_user_data = {
        "username": getattr(user, "username", None),
        "email": getattr(user, "email", None),
        "mfa_enabled": getattr(user, "mfa_enabled", None),
        "language": getattr(user, "language", None),
        "dark_mode": getattr(user, "dark_mode", None),
        "city": getattr(user, "city", None),
        # add other fields as needed
    }

    for field, new_value in user_data.items():
        current_value = current_user_data.get(field)
        if current_value is None or str(current_value) != str(new_value):
            print(field)
            changed_fields[field] = {"old": current_value, "new": new_value}
            setattr(user, field, new_value)

    if changed_fields:
        # Update the user's document in the database
        mongo.users.update_one({"_id": user._id}, {"$set": user_data})

        # Send an email notification about the changes
        try:
            email_sender.queue_email(
                template_name="auth/settings_changed.html",
                subject="Käyttäjäasetusten muutokset",
                recipients=[user.email],
                context={
                    "changed_fields": changed_fields,
                    "user_name": user.displayname or user.username,
                },
            )
        except Exception as e:
            flash_message(f"Virhe asetusten muutosviestin lähettämisessä: {e}", "error")

        # Start the process associated with the changed settings
        process_settings_change(user, changed_fields)

        return jsonify({
            "status": "success",
            "message": "Asetukset päivitetty ja ilmoitus lähetetty.",
            "changed_fields": changed_fields
        })
    else:
        return jsonify({
            "status": "success",
            "message": "Ei muutoksia asetuksissa."
        })


def process_settings_change(user, changed_fields):
    """
    Start the process for handling changed settings.

    Parameters
    ----------
    user : User
        The current user object.
    changed_fields : dict
        A dictionary containing the fields that were changed.
    """
    # This is a placeholder for any additional process that should be started.
    current_app.logger.info(f"User {user._id} settings changed: {changed_fields}")
    from bson import ObjectId
    for changed_field, values in changed_fields.items():
        current_app.logger.info(f" - {changed_field}: {values['old']} -> {values['new']}")
    print(changed_fields)
    if "display_name" in changed_fields:
        user.displayname = changed_fields["display_name"]["new"]
        print("Updated display name to the user object too")
        user.save()

@auth_bp.route("/api/v2/settings", methods=["GET", "POST"])
@login_required
def settings_api_v2():
    """
    Get or update general user settings (city, display_name, language, dark_mode, subscribe_newsletter)
    in a single collection 'user_settings'. MFA is handled separately in /api/v2/mfa.
    """
    user = current_user
    allowed_fields = {
        "city",
        "display_name",
        "language",
        "dark_mode",
        "subscribe_newsletter",
    }

    # Ensure user has a settings document
    sett = mongo.user_settings.find_one({"user_id": ObjectId(user._id)})
    if not sett:
        sett = {field: None for field in allowed_fields}
        sett["display_name"] = getattr(user, "displayname", user.username)
        sett["user_id"] = ObjectId(user._id)
        mongo.user_settings.insert_one(sett)

    # ---------- GET ----------
    if request.method == "GET":
        current_user_data = {field: sett.get(field) for field in allowed_fields}
        return jsonify({
            "status": "success",
            "settings": current_user_data
        })

    # ---------- POST ----------
    if request.is_json:
        user_data = request.get_json(force=True)
    else:
        user_data = request.form.to_dict()

    changed_fields = {}
    update_data = {}

    for field in allowed_fields:
        if field not in user_data:
            continue
        new_value = user_data[field]
        current_value = sett.get(field)

        # try parse JSON for structured fields
        if isinstance(new_value, str):
            try:
                new_value = json.loads(new_value)
            except Exception:
                pass

        if current_value != new_value:
            changed_fields[field] = {"old": current_value, "new": new_value}
            update_data[field] = new_value
            setattr(user, field, new_value)  # update in-memory user object
            print(f"Changed {field}: {current_value} -> {new_value}")

    if changed_fields:
        mongo.user_settings.update_one(
            {"user_id": ObjectId(user._id)},
            {"$set": update_data}
        )

        # notify by email
        try:
            email_sender.queue_email(
                template_name="auth/settings_changed.html",
                subject="Käyttäjäasetusten muutokset",
                recipients=[user.email],
                context={
                    "changed_fields": changed_fields,
                    "user_name": getattr(user, "displayname", user.username),
                },
            )
        except Exception as e:
            flash_message(f"Virhe asetusten muutosviestin lähettämisessä: {e}", "error")

        process_settings_change(user, changed_fields)

        return jsonify({
            "status": "success",
            "message": "Asetukset päivitetty ja ilmoitus lähetetty.",
            "changed_fields": changed_fields
        })

    return jsonify({
        "status": "success",
        "message": "Ei muutoksia asetuksissa."
    })

@auth_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    """Let users activate MFA"""
    user = current_user

    

    return render_template("users/auth/settings.html", user=user)

# --- Update MFA API to handle multiple devices ---
@auth_bp.route("/api/v2/mfa", methods=["POST"])
@login_required
def mfa_setup_api():
    """
    MFA Setup API supporting multiple devices.
    Steps:
    1) request_activation: generates secret + QR, stores in pending_mfa
    2) verify_code: user submits current TOTP code, server verifies and activates
    3) done: just returns success
    """
    user = current_user
    data = request.get_json(force=True)
    step = data.get("step")

    if step == "request_activation":
        # Step 1: generate secret for new device
        secret = PendingMFA.create(user._id)
        user_mfa = UserMFA(user._id)
        qr_code_url = user_mfa.get_qr_code_url(secret)
        qr_code_base64 = f"data:image/png;base64,{generate_qr(qr_code_url)}"
        return jsonify({
            "status": "pending",
            "qr_code": qr_code_base64,
            "secret": secret
        })

    elif step == "verify_code":
        code = data.get("code")
        secret = data.get("secret")  # which secret we are verifying
        device_name = data.get("device_name", "New device")
        if not code or not secret:
            return jsonify({"status": "error", "message": "Code or secret missing"}), 400

        mfa_token = MFAToken(secret)
        if mfa_token.verify(code):
            mongo.mfas.insert_one({
                "user_id": user._id,
                "secret": secret,
                "device_name": device_name,
                "created_at": datetime.datetime.utcnow()
            })
            PendingMFA.delete(user._id, secret)
            user.mfa_enabled = True
            user.save()
            return jsonify({"status": "success", "message": "MFA aktivoitu!"})
        else:
            return jsonify({"status": "error", "message": "Väärä koodi"}), 400

    elif step == "done":
        return jsonify({"status": "success", "message": "MFA flow complete"})

    else:
        return jsonify({"status": "error", "message": "Invalid step"}), 400
    
# --- MFA Status Endpoint ---
@auth_bp.route("/api/v2/mfa_status", methods=["GET"])
@login_required
def mfa_status():
    """
    Returns MFA status and list of active devices/secrets for the current user.
    """
    user = current_user
    user_mfa_records = mongo.mfas.find({"user_id": user._id})
    devices = []
    for rec in user_mfa_records:
        devices.append({
            "id": str(rec["_id"]),
            "name": rec.get("device_name", "Unknown device"),
            "created_at": rec.get("created_at").strftime("%Y-%m-%d %H:%M")
        })
    
    return jsonify({
        "status": "enabled" if user.mfa_enabled else "disabled",
        "devices": devices
    })


# --- MFA Device Revoke Endpoint ---
@auth_bp.route("/api/v2/mfa_device_revoke", methods=["POST"])
@login_required
def mfa_device_revoke():
    """
    Removes a specific MFA device/secret for the user.
    """
    user = current_user
    data = request.get_json(force=True)
    device_id = data.get("device_id")
    
    if not device_id:
        return jsonify({"status": "error", "message": "device_id is required"}), 400

    result = mongo.mfas.delete_one({"_id": device_id, "user_id": user._id})
    
    if result.deleted_count == 1:
        # Check if any devices remain, else disable MFA flag
        remaining = mongo.mfas.count_documents({"user_id": user._id})
        if remaining == 0:
            user.mfa_enabled = False
            user.save()
        return jsonify({"status": "success", "message": "Device removed"})
    else:
        return jsonify({"status": "error", "message": "Device not found"}), 404


@auth_bp.route("/logout")
@login_required
def logout():
    """ """
    logout_user()
    flash_message("Kirjauduit onnistuneesti ulos", "success")
    return redirect(url_for("users.auth.login"))


@auth_bp.route("/password_reset_request", methods=["GET", "POST"])
def password_reset_request():
    """
    Handles password reset requests without revealing whether an email exists.
    """
    if request.method == "POST":
        email = request.form.get("email")

        # Always show the same response, regardless of whether the user exists
        flash_message(
            "Jos sähköpostiosoite löytyy järjestelmästämme, "
            "salasanan palautuslinkki on lähetetty siihen.", 
            "info"
        )

        user = mongo.users.find_one({"email": email})
        if user:
            token = generate_reset_token(email)
            reset_url = url_for(
                "users.auth.password_reset", token=token, _external=True
            )
            try:
                email_sender.queue_email(
                    template_name="password_reset_email.html",
                    subject="Salasanan palautuspyyntö",
                    recipients=[email],
                    context={"reset_url": reset_url, "user_name": user.get("username")},
                )
            except Exception as e:
                # Fail silently — don’t reveal error details to the user
                # (optional: log the error internally)
                pass  

        return redirect(url_for("users.auth.login"))

    return render_template("users/auth/password_reset_request.html")
@auth_bp.route("/api/v2/user_profile", methods=["GET", "POST"])
def user_profile():
    """
    JSON-only endpoint for user bio + profile picture updates.
    Accepts:
    {
        "bio": "new bio text",
        "profile_picture": "<base64 string of image>"   # optional
    }
    """
    user = current_user

    if request.method == "POST":
        data = request.get_json(force=True)

        # Update bio
        bio = data.get("bio")
        if bio is not None:
            user.bio = bio

        # Handle profile picture (base64 string)
        profile_picture_b64 = data.get("profile_picture")
        if profile_picture_b64:
            try:
                # Decode base64 -> bytes

                # Generate filename
                filename = secure_filename(f"{user.id}.png")

                # Upload to S3
                bucket_name = current_app.config.get("S3_BUCKET")
                import io

                img_bytes = base64.b64decode(profile_picture_b64)
                img_stream = io.BytesIO(img_bytes)
             
                photo_url = upload_image_fileobj(bucket_name, img_stream, filename, "profile_pics")

                if photo_url:
                    user.profile_picture = photo_url
                else:
                    return jsonify({"status": "error", "message": "Error uploading image to S3"}), 500
            except Exception as e:
                return jsonify({"status": "error", "message": f"Invalid image data: {str(e)}"}), 400

        # Save changes in Mongo
        mongo.users.update_one(
            {"_id": ObjectId(user.id)},
            {
                "$set": {
                    "bio": getattr(user, "bio", None),
                    "profile_picture": getattr(user, "profile_picture", None),
                }
            },
        )

        return jsonify({"status": "success", "message": "Profile updated successfully"})

    # GET request - return user profile data
    return jsonify({
        "status": "success",
        "data": {
            "bio": getattr(user, "bio", None),
            "profile_picture": getattr(user, "profile_picture", None),
        }
    })
from datetime import datetime

@auth_bp.route("/password_reset/<token>", methods=["GET", "POST"])
def password_reset(token):
    """
    Handle password reset using a token, with full logging and single-use token enforcement.
    """
    ip = request.remote_addr
    user_agent = request.headers.get("User-Agent", "")
    
    # Check if token has already been used
    if mongo.used_password_change_tokens.find_one({"token": token}):
        flash_message(
            "Tämä salasanan palautuslinkki on jo käytetty.", "warning"
        )
        return redirect(url_for("users.auth.password_reset_request"))

    email = verify_reset_token(token)

    log_entry = {
        "token": token,
        "email": email or None,
        "datetime": datetime.utcnow(),
        "ip": ip,
        "user_agent": user_agent,
        "visit": True,
        "changed": False,
        "error": None,
    }

    if not email:
        log_entry["error"] = "Invalid or expired token"
        mongo.password_changes.insert_one(log_entry)
        flash_message(
            "Salasanan palautuslinkki on virheellinen tai vanhentunut.", "warning"
        )
        return redirect(url_for("users.auth.password_reset_request"))

    user_doc = mongo.users.find_one({"email": email})
    if not user_doc:
        log_entry["error"] = "User not found"
        mongo.password_changes.insert_one(log_entry)
        flash_message("Käyttäjää ei löytynyt.", "warning")
        return redirect(url_for("users.auth.password_reset_request"))

    user = User.from_db(user_doc)

    if request.method == "POST":
        password = request.form.get("password")
        confirm_password = request.form.get("password_confirm")

        if password != confirm_password:
            log_entry["error"] = "Passwords do not match"
            mongo.password_changes.insert_one(log_entry)
            flash_message("Salasanat eivät täsmää!", "warning")
            return redirect(url_for("users.auth.password_reset", token=token))

        if not is_strong_password(password, username=user.username, email=email):
            log_entry["error"] = "Password does not meet requirements"
            mongo.password_changes.insert_one(log_entry)
            flash_message("Salasana ei täytä vaatimuksia.", "warning")
            return redirect(url_for("users.auth.password_reset", token=token))

        try:
            user._change_password(password)
            log_entry["changed"] = True
            mongo.password_changes.insert_one(log_entry)

            # Mark token as used
            mongo.used_password_change_tokens.insert_one({
                "token": token,
                "email": email,
                "used_at": datetime.utcnow(),
                "ip": ip,
                "user_agent": user_agent,
                "password_change_success": True
            })
        except Exception as e:
            log_entry["error"] = f"Password change failed: {e}"
            mongo.password_changes.insert_one(log_entry)
            flash_message(f"Salasanan vaihto epäonnistui: {e}", "error")
            return redirect(url_for("users.auth.password_reset", token=token))

        # Notify user via email
        try:
            email_sender.queue_email(
                template_name="auth/password_changed.html",
                subject="Salasanan vaihto",
                recipients=[email],
                context={"user_name": user.displayname or user.username},
            )
        except Exception as e:
            flash_message(f"Virhe salasanan vaihtoviestin lähettämisessä: {e}", "error")

        flash_message("Salasanasi on päivitetty onnistuneesti.", "success")
        return redirect(url_for("users.auth.login"))

    # Log GET visit
    mongo.password_changes.insert_one(log_entry)
    return render_template("users/auth/password_reset.html", token=token)

# NEXT STEPS:
# - Move all the stuff from edit profile to user profile settings
# - Create the emails/auth/settings_changed.html template to notify users about changes

# API ENDPOINT FOR GETTING:
    # - email
    # - username
    # - display name
    # - city
    # - dark mode
    
    # - language
    
    
@auth_bp.route("/api/v1/user_info", methods=["GET"])
@login_required
def user_info_api():
    """
    Returns basic user info + settings for the current user.
    Fields returned: email, display_name, city, dark_mode, language
    """
    user = current_user

    # Fetch the user's settings document
    sett = mongo.user_settings.find_one({"user_id": ObjectId(user._id)})
    if not sett:
        # If no settings doc exists, create one with defaults
        allowed_fields = {"display_name", "city", "dark_mode", "language"}
        sett = {field: None for field in allowed_fields}
        sett["display_name"] = getattr(user, "displayname", user.username)
        sett["user_id"] = ObjectId(user._id)
        mongo.user_settings.insert_one(sett)

    # Prepare the response using settings + email from the user object
    user_info = {
        "email": getattr(user, "email", None),
        "display_name": sett.get("display_name"),
        "city": sett.get("city"),
        "dark_mode": sett.get("dark_mode"),
        "language": sett.get("language"),
    }

    return jsonify({"status": "success", "user_info": user_info})


# ── users/auth/api additions ──────────────────────────────────────────────────
from datetime import datetime
from werkzeug.security import check_password_hash

# ── 1A.  Login-logs feed ─────────────────────────────────────────────────────
@auth_bp.route("/api/v2/login_logs")
@login_required
def api_login_logs():
    """
    Return latest login attempts for the current user.
      GET  /users/auth/api/v2/login_logs?limit=25
    """
    limit = int(request.args.get("limit", 20))
    cursor = (mongo.login_logs
                    .find({"user_id": current_user._id})
                    .sort("timestamp", -1)
                    .limit(limit))
    logs = []
    for row in cursor:
        logs.append({
            "time":   row["timestamp"].isoformat(),
            "ip":     row.get("ip"),
            "ua":     row.get("user_agent", "")[:120],
            "ok":     row["success"],
            "reason": row.get("reason", "")
        })
    return jsonify({"status": "success", "logs": logs})


# ── 1B.  Change-password endpoint for Settings page ──────────────────────────
@auth_bp.route("/api/v2/change_password", methods=["POST"])
@login_required
def api_change_password():
    """
    JSON-only password change:
    {
      "current": "<current pw>",
      "new":     "<new pw>",
      "confirm": "<repeat>"
    }
    """
    data = request.get_json(force=True)
    cur, new, confirm = data.get("current"), data.get("new"), data.get("confirm")

    if not all((cur, new, confirm)):
        return jsonify({"status": "error",
                        "message": "All fields required."}), 400
    if new != confirm:
        return jsonify({"status": "error",
                        "message": "Passwords do not match."}), 400
    if not current_user.check_password(cur):
        return jsonify({"status": "error",
                        "message": "Current password is wrong."}), 400
    if not is_strong_password(new,
                              username=current_user.username,
                              email=current_user.email):
        return jsonify({"status": "error",
                        "message": "Password too weak."}), 400

    # actually change & log
    current_user._change_password(new)
    mongo.password_changes.insert_one({
        "user_id": current_user._id,
        "datetime": datetime.utcnow(),
        "ip": request.remote_addr,
        "user_agent": request.headers.get("User-Agent", ""),
        "method": "settings_page",
        "changed": True
    })

    # optional mail
    try:
        email_sender.queue_email(
            template_name="auth/password_changed.html",
            subject="Salasanasi on vaihdettu",
            recipients=[current_user.email],
            context={"user_name": current_user.displayname or current_user.username},
        )
    except Exception:
        pass

    return jsonify({"status": "success", "message": "OK"})
