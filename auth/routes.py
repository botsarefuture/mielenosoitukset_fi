from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort,
    current_app,
)
from flask_login import login_user, logout_user, login_required, current_user
from auth.models import User
import jwt
import datetime
from emailer.EmailSender import EmailSender
from bson.objectid import ObjectId
from database_manager import DatabaseManager
from s3_utils import upload_image  # Import your S3 upload function
import os

db_manager = DatabaseManager().get_instance()
mongo = db_manager.get_db()

email_sender = EmailSender()
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
            flash(
                "Virheellinen syöte. Käyttäjänimen tulee olla vähintään 3 merkkiä pitkä ja salasanan vähintään 6 merkkiä pitkä.",
                "error",
            )
            return redirect(url_for("auth.register"))

        if mongo.users.find_one({"username": username}):
            flash("Käyttäjänimi on jo käytössä.", "warning")
            return redirect(url_for("auth.register"))

        if mongo.users.find_one({"email": email}):
            flash(
                "Sähköpostiosoite on jo rekisteröity. Kirjaudu sisään sen sijaan.",
                "warning",
            )
            return redirect(url_for("auth.login"))

        user_data = User.create_user(username, password, email)
        mongo.users.insert_one(user_data)

        try:
            verify_emailer(email, username)
            flash(
                "Rekisteröinti onnistui! Tarkista sähköpostisi vahvistaaksesi tilisi.",
                "info",
            )
        except Exception as e:
            flash(f"Virhe vahvistusviestin lähettämisessä: {e}", "error")

        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth_bp.route("/confirm_email/<token>")
def confirm_email(token):
    email = verify_confirmation_token(token)
    if email:
        user = mongo.users.find_one({"email": email})
        if user:
            mongo.users.update_one({"email": email}, {"$set": {"confirmed": True}})
            flash(
                "Sähköpostiosoitteesi on vahvistettu. Voit nyt kirjautua sisään.",
                "info",
            )
        else:
            flash("Käyttäjää ei löytynyt.", "error")
    else:
        flash("Vahvistuslinkki on virheellinen tai vanhentunut.", "warning")

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
            flash("Anna sekä käyttäjänimi että salasana.", "warning")
            return redirect(
                url_for("auth.login", next=next_page)
            )  # Pass next page along

        user_doc = mongo.users.find_one({"username": username})

        if not user_doc:
            flash(f"Käyttäjänimellä '{username}' ei löytynyt käyttäjiä.", "error")
            return redirect(url_for("auth.login", next=next_page))

        user = User.from_db(user_doc)
        if not user.check_password(password):
            flash("Käyttäjänimi tai salasana on väärin.", "error")
            return redirect(url_for("auth.login", next=next_page))

        if user.confirmed:
            login_user(user)
            return redirect(
                next_page or url_for("index")
            )  # Redirect to the next page or the index

        else:
            flash("Sähköpostiosoitettasi ei ole vahvistettu. Tarkista sähköpostisi.")
            verify_emailer(user.email, username)
            return redirect(next_page or url_for("index"))

    return render_template("login.html", next=next_page)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Kirjauduit onnistuneesti ulos", "success")
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
                flash("Salasanan palautuslinkki on lähetetty sähköpostiisi.", "info")
            except Exception as e:
                flash(f"Virhe salasanan palautusviestin lähettämisessä: {e}", "error")

            return redirect(url_for("auth.login"))

        flash("Tilin sähköpostiosoitetta ei löytynyt.", "info")
        return redirect(url_for("auth.password_reset_request"))

    return render_template("password_reset_request.html")


@auth_bp.route("/password_reset/<token>", methods=["GET", "POST"])
def password_reset(token):
    email = verify_reset_token(token)
    if not email:
        flash("Salasanan palautuslinkki on virheellinen tai vanhentunut.", "warning")
        return redirect(url_for("auth.password_reset_request"))

    if request.method == "POST":
        password = request.form.get("password")

        user_doc = mongo.users.find_one({"email": email})
        if not user_doc:
            flash("Käyttäjää ei löytynyt.", "warning")
            return redirect(url_for("auth.password_reset_request"))

        user = User.from_db(user_doc)
        user.change_password(mongo, password)

        flash("Salasanasi on päivitetty onnistuneesti.", "success")
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
        flash("Käyttäjäprofiilia ei löytynyt.", "warning")
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
            temp_file_path = os.path.join("uploads", profile_picture.filename)
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
                flash("Profiilitietosi on päivitetty.", "success")
            else:
                flash("Virhekuvan lataamisessa S3:een.", "error")

            # Clean up the temporary file
            os.remove(temp_file_path)

        return redirect(url_for("auth.profile", username=current_user.username))

    return render_template("edit_profile.html")


def generate_reset_token(email):
    return jwt.encode(
        {
            "email": email,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        },
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )


def verify_reset_token(token):
    try:
        data = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
        return data["email"]
    except Exception:
        return None


def generate_confirmation_token(email):
    return jwt.encode(
        {
            "email": email,
            "exp": datetime.datetime.utcnow()
            + datetime.timedelta(hours=1),  # Korjattu rivi
        },
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )


def verify_confirmation_token(token):
    try:
        data = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
        return data["email"]
    except Exception:
        return None
