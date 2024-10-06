from flask import Blueprint, redirect, url_for, flash, request
from flask_login import login_required, current_user
from auth.models import User  # Adjust the import based on your project structure
from database_manager import DatabaseManager  # Adjust based on your database setup

mongo = DatabaseManager().get_instance().get_db()

user_bp = Blueprint("user", __name__)


@user_bp.route("/follow/<username>", methods=["POST"])
@login_required
def follow(username):
    user_to_follow = User.from_db(mongo.users.find_one({"username": username}))
    if user_to_follow:
        current_user.follow_user(mongo, user_to_follow.id)
        flash(f"Olet nyt seuraamassa käyttäjää {username}.", "success")
    else:
        flash("Käyttäjää ei löytynyt.", "danger")
    return redirect(request.referrer)  # Replace with the appropriate view


@user_bp.route("/unfollow/<username>", methods=["POST"])
@login_required
def unfollow(username):
    user_to_unfollow = User.from_db(mongo.users.find_one({"username": username}))
    if user_to_unfollow:
        current_user.unfollow_user(mongo, user_to_unfollow.id)
        flash(f"Lopetit käyttäjän {username} seuraamisen.", "success")
    else:
        flash("Käyttäjää ei löytynyt.", "danger")
    return redirect(request.referrer)  # Replace with the appropriate view
