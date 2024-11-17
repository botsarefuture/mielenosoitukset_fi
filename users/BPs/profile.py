from flask import Blueprint, render_template, request, redirect, url_for, abort
from flask_login import current_user, login_required
from bson.objectid import ObjectId
from database_manager import DatabaseManager
from utils.flashing import flash_message
from werkzeug.utils import secure_filename
import os

from users.models import User
from utils.s3 import upload_image
from utils.logger import logger

mongo = DatabaseManager().get_instance().get_db()

profile_bp = Blueprint("profile", __name__, template_folder="/users/profile/", url_prefix="/profile")

@profile_bp.route("/")
@profile_bp.route("/<username>")
def profile(username=None):
    if username is None:
        if current_user.is_authenticated:
            username = current_user.username
        else:
            return abort(404)

    user = mongo.users.find_one({"username": username})
    if user:
        user_data = User.from_db(user)
        return render_template("users/profile/profile.html", user=user_data)
    else:
        flash_message("Käyttäjäprofiilia ei löytynyt.", "warning")
        return redirect(url_for("index"))

@profile_bp.route("/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        displayname = request.form.get("displayname")
        bio = request.form.get("bio")
        profile_picture = request.files.get("profile_picture")

        current_user.displayname = displayname
        current_user.bio = bio

        if profile_picture:
            filename = secure_filename(profile_picture.filename)
            temp_file_path = os.path.join("uploads", filename)
            profile_picture.save(temp_file_path)

            bucket_name = "mielenosoitukset-fi1"
            photo_url = upload_image(bucket_name, temp_file_path, "profile_pics")

            if photo_url:
                current_user.profile_picture = photo_url
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

            os.remove(temp_file_path)

        return redirect(url_for("profile.profile", username=current_user.username))

    return render_template("users/profile/edit_profile.html")


@profile_bp.route("/follow/<username>", methods=["POST"])
@login_required
def follow(username):
    try:
        user_to_follow = User.from_db(mongo.users.find_one({"username": username}))
        logger.debug(f"User to follow: {user_to_follow}")
        if user_to_follow:
            current_user.follow_user(user_to_follow.id)
            flash_message(f"Seuraat nyt käyttäjää {username}.", "success")
            logger.debug(f"User {current_user.username} followed {username}.")
        else:
            flash_message("Käyttäjää ei löytynyt.", "danger")
            logger.warning(f"User {username} not found for following.")
            
    except Exception as e:
        flash_message("Tapahtui virhe.", "danger")
        logger.error(f"Error following user {username}: {e}")
        
    return redirect(request.referrer or "/")  # TODO: #197 Use safe referrer // redirect to home if referrer is not available

@profile_bp.route("/unfollow/<username>", methods=["POST"])
@login_required
def unfollow(username):
    try:
        user_to_unfollow = User.from_db(mongo.users.find_one({"username": username}))
        if user_to_unfollow:
            current_user.unfollow_user(user_to_unfollow.id)
            
            flash_message(f"Lopetit käyttäjän {username} seuraamisen.", "success")
            
            logger.debug(f"User {current_user.username} unfollowed {username}.")
        else:
            flash_message("Käyttäjää ei löytynyt", "danger")
            
            logger.warning(f"User {username} not found for unfollowing.")
            
    except Exception as e:
        flash_message("Tapahtui virhe.", "danger")
        logger.error(f"Error unfollowing user {username}: {e}")
        
    return redirect(request.referrer)  # TODO: #197 Use safe referrer // redirect to home if referrer is not available
