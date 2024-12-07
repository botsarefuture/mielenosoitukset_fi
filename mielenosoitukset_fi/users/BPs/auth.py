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


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    next_page = request.args.get("next", "")
    next_page = next_page.replace("\\", "")
    if not urlparse(next_page).netloc and not urlparse(next_page).scheme:
        safe_next_page = next_page
    else:
        safe_next_page = url_for("index")

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            flash_message("Anna sekä käyttäjänimi että salasana.", "warning")
            return redirect(url_for("users.auth.login", next=next_page))

        user_doc = mongo.users.find_one({"username": username})

        if not user_doc:
            flash_message(
                f"Käyttäjänimellä '{username}' ei löytynyt käyttäjiä.", "error"
            )
            return redirect(url_for("users.auth.login", next=next_page))

        user = User.from_db(user_doc)
        if not user.check_password(password):
            flash_message("Käyttäjänimi tai salasana on väärin.", "error")
            return redirect(url_for("users.auth.login", next=next_page))

        if not user.confirmed:
            flash_message(
                "Sähköpostiosoitettasi ei ole vahvistettu. Tarkista sähköpostisi."
            )
            verify_emailer(user.email, username)
            return redirect(url_for("users.auth.login", next=next_page))

        if user.mfa_enabled:
            session["mfa_required"] = True
            session["modified"] = True
            return redirect(url_for("users.auth.verify_mfa", next=next_page))

        login_user(user)
        return redirect(next_page or url_for("index"))

    return render_template("users/auth/login.html", next=next_page)


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
    if user.mfa_enabled and not user.mfa_secret:
        user_mfa = user.mfa
        secret = user_mfa.generate_secret()
        print(secret)
        # mongo.users.update_one({"_id": user._id}, {"$set": {"mfa_secret": user_mfa.secret}})
        # user.mfa.add_secret = user_mfa.secret

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
