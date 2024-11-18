from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    current_app,
)
from flask_login import login_user, logout_user, login_required, current_user
from users.models import User
from utils.auth import (
    generate_confirmation_token,
    verify_confirmation_token,
    generate_reset_token,
    verify_reset_token,
)
from utils.flashing import flash_message
from utils.s3 import upload_image
from database_manager import DatabaseManager
from classes import Organization
from bson.objectid import ObjectId
from werkzeug.utils import secure_filename
import importlib
import os
import jwt
import datetime

EmailSender = importlib.import_module('emailer.EmailSender', "mielenosoitukset_fi").EmailSender

email_sender = EmailSender()
db_manager = DatabaseManager().get_instance()
mongo = db_manager.get_db()

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def verify_emailer(email, username):
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
    next_page = request.args.get("next")

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            flash_message("Anna sekä käyttäjänimi että salasana.", "warning")
            return redirect(url_for("users.auth.login", next=next_page))

        user_doc = mongo.users.find_one({"username": username})

        if not user_doc:
            flash_message(f"Käyttäjänimellä '{username}' ei löytynyt käyttäjiä.", "error")
            return redirect(url_for("users.auth.login", next=next_page))

        user = User.from_db(user_doc)
        if not user.check_password(password):
            flash_message("Käyttäjänimi tai salasana on väärin.", "error")
            return redirect(url_for("users.auth.login", next=next_page))

        if user.confirmed:
            login_user(user)
            return redirect(next_page or url_for("index"))
        else:
            flash_message("Sähköpostiosoitettasi ei ole vahvistettu. Tarkista sähköpostisi.")
            verify_emailer(user.email, username)
            return redirect(next_page or url_for("index"))

    return render_template("users/auth/login.html", next=next_page)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash_message("Kirjauduit onnistuneesti ulos", "success")
    return redirect(url_for("users.auth.login"))


@auth_bp.route("/password_reset_request", methods=["GET", "POST"])
def password_reset_request():
    if request.method == "POST":
        email = request.form.get("email")
        user = mongo.users.find_one({"email": email})

        if user:
            token = generate_reset_token(email)
            reset_url = url_for("users.auth.password_reset", token=token, _external=True)

            try:
                email_sender.queue_email(
                    template_name="password_reset_email.html",
                    subject="Salasanan palautuspyyntö",
                    recipients=[email],
                    context={"reset_url": reset_url, "user_name": user.get("username")},
                )
                flash_message("Salasanan palautuslinkki on lähetetty sähköpostiisi.", "info")
            except Exception as e:
                flash_message(f"Virhe salasanan palautusviestin lähettämisessä: {e}", "error")

            return redirect(url_for("users.auth.login"))

        flash_message("Tilin sähköpostiosoitetta ei löytynyt.", "info")
        return redirect(url_for("users.auth.password_reset_request"))

    return render_template("users/auth/password_reset_request.html")


@auth_bp.route("/password_reset/<token>", methods=["GET", "POST"])
def password_reset(token):
    email = verify_reset_token(token)
    if not email:
        flash_message("Salasanan palautuslinkki on virheellinen tai vanhentunut.", "warning")
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
