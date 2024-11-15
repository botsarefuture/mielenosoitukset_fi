from flask import Blueprint, redirect, request
from auth.models import User
from flask_login import login_required, current_user

from database_manager import DatabaseManager
from utils.flashing import flash_message
from utils.logger import logger


mongo = DatabaseManager().get_instance().get_db()

user_bp = Blueprint("user", __name__)

@user_bp.route("/follow/<username>", methods=["POST"])
@login_required
def follow(username):
    try:
        user_to_follow = User.from_db(mongo.users.find_one({"username": username}))
        print(user_to_follow)
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

@user_bp.route("/unfollow/<username>", methods=["POST"])
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
