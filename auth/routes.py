from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    abort,
    current_app,
)
from flask_login import login_user, logout_user, login_required, current_user
from auth.models import User
import jwt
import datetime
import importlib

from utils.auth import (
    generate_confirmation_token,
    verify_confirmation_token,
    generate_reset_token,
    verify_reset_token,
    
)

EmailSender = importlib.import_module('emailer.EmailSender', "mielenosoitukset_fi").EmailSender
from bson.objectid import ObjectId
from database_manager import DatabaseManager
from utils.s3 import upload_image  # Import your S3 upload function
import os
from utils.flashing import flash_message
from werkzeug.utils import secure_filename

email_sender = EmailSender()  # Initialize email sender
db_manager = DatabaseManager().get_instance()
mongo = db_manager.get_db()

auth_bp = Blueprint("auth", __name__, template_folder="./templates/")


def verify_emailer(email, username):
    token = generate_confirmation_token(email)
    confirmation_url = url_for("auth.confirm_email", token=token, _external=True)

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
            return redirect(url_for("auth.register"))

        if mongo.users.find_one({"username": username}):
            flash_message("Käyttäjänimi on jo käytössä.", "warning")
            return redirect(url_for("auth.register"))

        if mongo.users.find_one({"email": email}):
            flash_message(
                "Sähköpostiosoite on jo rekisteröity. Kirjaudu sisään sen sijaan.",
                "warning",
            )
            return redirect(url_for("auth.login"))

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

        return redirect(url_for("auth.login"))

    return render_template("register.html")


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

    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # Get the next URL to redirect to after login
    next_page = request.args.get(
        "next"
    )  # Get the 'next' parameter from the query string

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            flash_message("Anna sekä käyttäjänimi että salasana.", "warning")
            return redirect(
                url_for("auth.login", next=next_page)
            )  # Pass next page along

        user_doc = mongo.users.find_one({"username": username})

        if not user_doc:
            flash_message(
                f"Käyttäjänimellä '{username}' ei löytynyt käyttäjiä.", "error"
            )
            return redirect(url_for("auth.login", next=next_page))

        user = User.from_db(user_doc)
        if not user.check_password(password):
            flash_message("Käyttäjänimi tai salasana on väärin.", "error")
            return redirect(url_for("auth.login", next=next_page))

        if user.confirmed:
            login_user(user)
            return redirect(
                next_page or url_for("index")
            )  # Redirect to the next page or the index

        else:
            flash_message(
                "Sähköpostiosoitettasi ei ole vahvistettu. Tarkista sähköpostisi."
            )
            verify_emailer(user.email, username)
            return redirect(next_page or url_for("index"))

    return render_template("login.html", next=next_page)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash_message("Kirjauduit onnistuneesti ulos", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/password_reset_request", methods=["GET", "POST"])
def password_reset_request():
    if request.method == "POST":
        email = request.form.get("email")
        user = mongo.users.find_one({"email": email})

        if user:
            token = generate_reset_token(email)
            reset_url = url_for("auth.password_reset", token=token, _external=True)

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

            return redirect(url_for("auth.login"))

        flash_message("Tilin sähköpostiosoitetta ei löytynyt.", "info")
        return redirect(url_for("auth.password_reset_request"))

    return render_template("password_reset_request.html")


@auth_bp.route("/password_reset/<token>", methods=["GET", "POST"])
def password_reset(token):
    email = verify_reset_token(token)
    if not email:
        flash_message(
            "Salasanan palautuslinkki on virheellinen tai vanhentunut.", "warning"
        )
        return redirect(url_for("auth.password_reset_request"))

    if request.method == "POST":
        password = request.form.get("password")

        user_doc = mongo.users.find_one({"email": email})
        if not user_doc:
            flash_message("Käyttäjää ei löytynyt.", "warning")
            return redirect(url_for("auth.password_reset_request"))

        user = User.from_db(user_doc)
        user.change_password(mongo, password)

        flash_message("Salasanasi on päivitetty onnistuneesti.", "success")
        return redirect(url_for("auth.login"))

    return render_template("password_reset.html", token=token)


@auth_bp.route("/profile/")
@auth_bp.route("/profile/<username>")
def profile(username=None):
    if username is None:
        if current_user.is_authenticated:
            username = current_user.username

        else:
            return abort(404)

    user = mongo.users.find_one({"username": username})
    if user:
        user_data = User.from_db(user)
        return render_template("profile.html", user=user_data)
    else:
        flash_message("Käyttäjäprofiilia ei löytynyt.", "warning")
        return redirect(url_for("index"))


@auth_bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        displayname = request.form.get("displayname")
        bio = request.form.get("bio")
        profile_picture = request.files.get("profile_picture")  # Get the uploaded file

        current_user.displayname = displayname
        current_user.bio = bio

        # Handle profile picture upload
        if profile_picture:
            # Save the uploaded file temporarily
            filename = secure_filename(profile_picture.filename)
            temp_file_path = os.path.join("uploads", filename)
            profile_picture.save(temp_file_path)

            # Define the bucket name and upload the file
            bucket_name = "mielenosoitukset-fi1"  # Your S3 bucket name
            photo_url = upload_image(bucket_name, temp_file_path, "profile_pics")

            if photo_url:
                current_user.profile_picture = (
                    photo_url  # Save the URL to the current user
                )

                # Update user in MongoDB
                mongo.users.update_one(
                    {"_id": ObjectId(current_user.id)},
                    {
                        "$set": {
                            "displayname": current_user.displayname,
                            "profile_picture": current_user.profile_picture,
                            "bio": current_user.bio,
                        }
                    },
                )
                flash_message("Profiilitietosi on päivitetty.", "success")
            else:
                flash_message("Virhekuvan lataamisessa S3:een.", "error")

            # Clean up the temporary file
            os.remove(temp_file_path)

        return redirect(url_for("auth.profile", username=current_user.username))

    return render_template("edit_profile.html")

@auth_bp.route("/accept_invite", methods=["GET"])
#@login_required # Don't require login to accept invite
def accept_invite():
    if not current_user.is_authenticated:
        flash_message("Kirjaudu sisään liittyäksesi organisaatioon.", "info")
        return redirect(url_for("auth.login", next=request.url))
    
    organization_id = request.args.get("organization_id")
    organization = mongo.organizations.find_one({"_id": ObjectId(organization_id)})

    if organization["invitations"] and current_user.email in organization["invitations"]:
        organization["invitations"].remove(current_user.email)
        mongo.organizations.update_one(
            {"_id": ObjectId(organization_id)},
            {"$set": {"invitations": organization["invitations"]}},
        )
        # Add user to organization
        current_user.add_organization(organization_id)
        
    else:
        flash_message("Kutsua ei löytynyt.", "warning")
        return redirect(url_for("index"))

    flash_message(f"Liityit organisaatioon {organization.get('name')}.", "success")
    return redirect(url_for("org", org_id=organization_id))