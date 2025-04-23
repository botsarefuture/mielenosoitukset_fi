from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    current_app,
    session,
)
from urllib.parse import urlparse
from flask_login import login_user, logout_user, login_required, current_user
from mielenosoitukset_fi.users.models import User, UserMFA
from mielenosoitukset_fi.utils.auth import (
    generate_confirmation_token,
    verify_confirmation_token,
    generate_reset_token,
    verify_reset_token,
)
from mielenosoitukset_fi.utils.flashing import flash_message
from mielenosoitukset_fi.utils.s3 import upload_image
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

        if not username or not password or len(username) < 3 or len(password) < 6:
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

        return redirect(url_for("users.auth.login"))

    return render_template("users/auth/register.html")


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

        return jsonify({"enabled": user.mfa_enabled, "valid": True})

    except Exception as e:
        return jsonify({"enabled": False, "valid": False})


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    next_page = request.args.get("next", "")
    next_page = next_page.replace("\\", "")
    
    if not next_page and session.get("next_page"):
        next_page = session.get("next_page")
        
    
    if not urlparse(next_page).netloc and not urlparse(next_page).scheme:
        safe_next_page = next_page
    else:
        safe_next_page = url_for("index")
        
    session["next_page"] = safe_next_page
    session.modified = True

    if request.method == "POST":
        let_login = True
        
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            flash_message("Anna sekä käyttäjänimi että salasana.", "warning")
            let_login = False
            return redirect(url_for("users.auth.login", next=safe_next_page))

        user_doc = mongo.users.find_one({"username": username})

        if not user_doc:
            let_login = False
            flash_message(
                f"Käyttäjänimellä '{username}' ei löytynyt käyttäjiä.", "error"
            )
            return redirect(url_for("users.auth.login", next=safe_next_page))

        user = User.from_db(user_doc)
        if not user.check_password(password):
            let_login = False
            flash_message("Käyttäjänimi tai salasana on väärin.", "error")
            return redirect(url_for("users.auth.login", next=safe_next_page))

        if not user.confirmed:
            let_login = False
            flash_message(
                "Sähköpostiosoitettasi ei ole vahvistettu. Tarkista sähköpostisi."
            )
            verify_emailer(user.email, username)
            return redirect(url_for("users.auth.login", next=safe_next_page))

        if user.mfa_enabled and not meow(user):
            let_login = False
            return redirect(url_for("users.auth.login", next=safe_next_page))

        
        if let_login:
            login_user(user)
            
        else:
            flash_message("Kirjautuminen epäonnistui.", "error")
            return redirect(url_for("users.auth.login", next=safe_next_page))
            
        return redirect(safe_next_page)

    return render_template("users/auth/login.html", next=safe_next_page)


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

@auth_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    """Let users activate MFA"""
    user = current_user

    if request.method == "POST":
        user_data = request.form.to_dict()

        if "mfa_enabled" in user_data:
            user_data["mfa_enabled"] = user_data["mfa_enabled"] == "on"
            mongo.users.update_one(
                {"_id": user._id}, {"$set": {"mfa_enabled": user_data["mfa_enabled"]}}
            )
            user.enable_mfa() if user_data["mfa_enabled"] else user.disable_mfa()

            # Send the user email, including the info on how to start using mfa
            if user_data["mfa_enabled"]:
                try:
                    email_sender.queue_email(
                        template_name="auth/mfa_enabled.html",
                        subject="Kaksivaiheisen todennuksen käyttöönotto",
                        recipients=[user.email],
                        context={"user_name": user.displayname or user.username},
                    )
                except Exception as e:
                    flash_message(
                        f"Virhe kaksivaiheisen todennuksen käyttöönoton viestin lähettämisessä: {e}",
                        "error",
                    )
            else:
                try:
                    email_sender.queue_email(
                        template_name="auth/mfa_disabled.html",
                        subject="Kaksivaiheisen todennuksen poistaminen",
                        recipients=[user.email],
                        context={"user_name": user.displayname or user.username},
                    )
                except Exception as e:
                    flash_message(
                        f"Virhe kaksivaiheisen todennuksen poistamisen viestin lähettämisessä: {e}",
                        "error",
                    )

        flash_message("Asetukset päivitetty.", "success")
        return redirect(url_for("users.auth.settings"))

    # return render_template("users/auth/settings.html", user=user)
    if user.mfa_enabled:
        user_mfa = UserMFA(user._id)
        secret = user_mfa.generate_secret()
        qr_code_url = user_mfa.get_qr_code_url()
        qr_code = generate_qr(qr_code_url)
        qr_code_base64 = f"data:image/png;base64,{qr_code}"

        return render_template(
            "users/auth/settings.html", user=user, qr_code_url=qr_code_base64
        )
    if user.mfa_enabled:
        user_mfa = user.mfa
        qr_code_url = user_mfa.get_qr_code_url()
        return render_template(
            "users/auth/settings.html", user=user, qr_code_url=qr_code_url
        )

    return render_template("users/auth/settings.html", user=user)


@auth_bp.route("/logout")
@login_required
def logout():
    """ """
    logout_user()
    flash_message("Kirjauduit onnistuneesti ulos", "success")
    return redirect(url_for("users.auth.login"))


@auth_bp.route("/password_reset_request", methods=["GET", "POST"])
def password_reset_request():
    """ """
    if request.method == "POST":
        email = request.form.get("email")
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
                flash_message(
                    "Salasanan palautuslinkki on lähetetty sähköpostiisi.", "info"
                )
            except Exception as e:
                flash_message(
                    f"Virhe salasanan palautusviestin lähettämisessä: {e}", "error"
                )

            return redirect(url_for("users.auth.login"))

        flash_message("Tilin sähköpostiosoitetta ei löytynyt.", "info")
        return redirect(url_for("users.auth.password_reset_request"))

    return render_template("users/auth/password_reset_request.html")


@auth_bp.route("/password_reset/<token>", methods=["GET", "POST"])
def password_reset(token):
    """

    Parameters
    ----------
    token :


    Returns
    -------


    """
    email = verify_reset_token(token)
    if not email:
        flash_message(
            "Salasanan palautuslinkki on virheellinen tai vanhentunut.", "warning"
        )
        return redirect(url_for("users.auth.password_reset_request"))

    if request.method == "POST":
        password = request.form.get("password")

        user_doc = mongo.users.find_one({"email": email})
        if not user_doc:
            flash_message("Käyttäjää ei löytynyt.", "warning")
            return redirect(url_for("users.auth.password_reset_request"))

        user = User.from_db(user_doc)
        user.change_password(password)

        # Notify user about their password being changed via email
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

    return render_template("users/auth/password_reset.html", token=token)


# TODO:
# - Add MFAs
# - Add user roles and permissions
# - Add password reset
# - Add settings page
#   - Language
#   - Notification settings
#   - Profile settings
