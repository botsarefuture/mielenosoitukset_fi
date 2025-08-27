from flask import Blueprint, current_app, render_template, request, redirect, url_for, abort
from urllib.parse import urlparse
from flask_login import current_user, login_required
from bson.objectid import ObjectId
from requests_cache import datetime
from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.database import stringify_object_ids
from mielenosoitukset_fi.utils.flashing import flash_message
from werkzeug.utils import secure_filename
import os

from mielenosoitukset_fi.users.models import User
from mielenosoitukset_fi.utils.s3 import upload_image_fileobj
from mielenosoitukset_fi.utils.logger import logger

mongo = DatabaseManager().get_instance().get_db()

profile_bp = Blueprint(
    "profile", __name__, template_folder="/users/profile/", url_prefix="/profile"
)


@profile_bp.route("/")
@profile_bp.route("/<username>")
def profile(username=None):
    """

    Parameters
    ----------
    username :
        Default value = None)

    Returns
    -------


    """
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
    """ """
    return redirect(url_for("users.auth.settings"))

@profile_bp.route("/api/is_following/")
@login_required
def api_is_following():
    username = request.args.get("username")
    if not username:
        return {"error": "Username is required"}, 400

    user_to_check_data = mongo.users.find_one({"username": username})
    if not user_to_check_data:
        return {"error": "User not found"}, 404

    user_to_check = User.from_db(user_to_check_data)
    is_following = current_user.am_i_following(user_to_check)  # use unified method

    return {"is_following": is_following}, 200


@profile_bp.route("/api/is_friends/")
@login_required
def api_is_friends():
    username = request.args.get("username")
    if not username:
        return {"error": "Username is required"}, 400

    user_to_check_data = mongo.users.find_one({"username": username})
    if not user_to_check_data:
        return {"error": "User not found"}, 404

    user_to_check = User.from_db(user_to_check_data)
    return {
        "is_following": current_user.am_i_following(user_to_check),
        "is_friends": current_user.is_friends_with(user_to_check)
    }, 200



@profile_bp.route("/api/follow/", methods=["POST"])
@login_required
def follow_user():
    data = request.json
    username = data.get("username")
    if not username:
        return {"error": "Username required"}, 400

    user_to_follow = User.from_db(mongo.users.find_one({"username": username}))
    if not user_to_follow:
        return {"error": "User not found"}, 404

    if current_user.am_i_following(user_to_follow):
        return {"error": "Already following"}, 400

    current_user.following.append(user_to_follow.id)
    user_to_follow.followers.append(current_user.id)
    current_user.save()
    user_to_follow.save()
    return {"success": True, "is_following": True}, 200


@profile_bp.route("/api/unfollow/", methods=["POST"])
@login_required
def unfollow_user():
    data = request.json
    username = data.get("username")
    if not username:
        return {"error": "Username required"}, 400

    user_to_unfollow = User.from_db(mongo.users.find_one({"username": username}))
    if not user_to_unfollow:
        return {"error": "User not found"}, 404

    if not current_user.am_i_following(user_to_unfollow):
        return {"error": "Not following"}, 400

    current_user.following.remove(user_to_unfollow.id)
    user_to_unfollow.followers.remove(current_user.id)
    current_user.save()
    user_to_unfollow.save()
    return {"success": True, "is_following": False}, 200
@profile_bp.route("/api/send_friend_request/", methods=["POST"])
@login_required
def send_friend_request():
    data = request.json
    username = data.get("username")
    if not username:
        return {"error": "Username required"}, 400

    other_data = mongo.users.find_one({"username": username})
    if not other_data:
        return {"error": "User not found"}, 404

    other = User.from_db(other_data)

    # Already friends?
    if any(f["user_id"] == other._id for f in current_user.friends):
        return {"error": "Already friends"}, 400

    # Request already sent?
    if any(req["sent_by"] == current_user._id for req in other.friend_requests):
        return {"error": "Request already sent"}, 400

    other.friend_requests.append({
        "sent_by": current_user._id,
        "sent_at": datetime.utcnow(),
        "sent_ip": request.remote_addr
    })
    other.save()
    return {"success": True, "status": "request_sent"}, 200

@profile_bp.route("/api/accept_friend_request/", methods=["POST"])
@login_required
def accept_friend_request():
    data = request.json
    username = data.get("username")
    if not username:
        return {"error": "Username required"}, 400

    other_data = mongo.users.find_one({"username": username})
    if not other_data:
        return {"error": "User not found"}, 404

    other = User.from_db(other_data)

    # Find request
    req = next((r for r in current_user.friend_requests if r["sent_by"] == other._id), None)
    if not req:
        return {"error": "No friend request from this user"}, 400

    # Remove request
    current_user.friend_requests = [r for r in current_user.friend_requests if r["sent_by"] != other._id]

    # Add friends with last_updated
    current_user.friends.append({"user_id": other._id, "last_updated": datetime.utcnow()})
    other.friends.append({"user_id": current_user._id, "last_updated": datetime.utcnow()})

    current_user.save()
    other.save()
    return {"success": True, "status": "friends"}, 200

@profile_bp.route("/api/reject_friend_request/", methods=["POST"])
@login_required
def reject_friend_request():
    data = request.json
    username = data.get("username")
    if not username:
        return {"error": "Username required"}, 400

    other_data = mongo.users.find_one({"username": username})
    if not other_data:
        return {"error": "User not found"}, 404

    other = User.from_db(other_data)

    # Remove request if exists
    current_user.friend_requests = [r for r in current_user.friend_requests if r["sent_by"] != other._id]
    current_user.save()
    return {"success": True, "status": "rejected"}, 200

@profile_bp.route("/api/friend_state/")
@login_required
def friend_state():
    username = request.args.get("username")
    if not username:
        return {"error": "Username required"}, 400

    other_data = mongo.users.find_one({"username": username})
    if not other_data:
        return {"error": "User not found"}, 404

    other = User.from_db(other_data)

    # check friends
    if any(f.get("user_id", f) == other._id for f in current_user.friends):
        state = "friends"
    # check incoming request
    elif any((r.get("sent_by", r) if isinstance(r, dict) else r) == other._id for r in current_user.friend_requests):
        state = "incoming_request"
    # check outgoing request
    elif any((r.get("sent_by", r) if isinstance(r, dict) else r) == current_user._id for r in other.friend_requests):
        state = "outgoing_request"
    else:
        state = "none"

    return {"friend_state": state}, 200


@profile_bp.route("/follow/<username>", methods=["POST"])
@login_required
def follow(username):
    """

    Parameters
    ----------
    username :


    Returns
    -------


    """
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

    referrer = request.referrer or "/"
    referrer = referrer.replace("\\", "")
    if not urlparse(referrer).netloc and not urlparse(referrer).scheme:
        return redirect(referrer, code=302)
    return redirect("/", code=302)


@profile_bp.route("/unfollow/<username>", methods=["POST"])
@login_required
def unfollow(username):
    """

    Parameters
    ----------
    username :


    Returns
    -------


    """
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

    referrer = request.referrer or "/"
    referrer = referrer.replace("\\", "")
    if not urlparse(referrer).netloc and not urlparse(referrer).scheme:
        return redirect(referrer, code=302)
    return redirect("/", code=302)

from flask import jsonify

# Fetch messages (inbox) for current user
from bson import ObjectId
from datetime import datetime

# Get all friends
@profile_bp.route("/api/friends_list/", methods=["GET"])
@login_required
def api_friends_list():
    friends = []
    for friend in current_user.friends:
        fid = friend.get("user_id")
        f_user_data = mongo.users.find_one({"_id": fid})
        if f_user_data:
            f_user = User.from_db(f_user_data)
            friends.append({
                "username": f_user.username,
                "displayname": f_user.displayname or f_user.username,
                "profile_picture": f_user.profile_picture,
                "_id": str(f_user._id)
            })
    return {"friends": friends}, 200

@profile_bp.route("/api/messages/unread_count/", methods=["GET"])
@login_required
def api_unread_count():
    counts = {}
    for fid in current_user.friends:
        fid = fid.get("user_id")
        msgs = mongo.messages.count_documents({
            "sender_id": fid,
            "recipient_id": current_user._id,
            "read": False
        })
        f_user_data = mongo.users.find_one({"_id": fid})
        if f_user_data:
            f_user = User.from_db(f_user_data)
            counts[f_user.username] = msgs
    return counts, 200




# Get messages between me and a specific friend
@profile_bp.route("/api/messages/<friend_username>/", methods=["GET"])
@login_required
def api_messages_with(friend_username):
    friend_data = mongo.users.find_one({"username": friend_username})

    # friends with:
    
    if not friend_data:
        return {"error": "Friend not found"}, 404
    friend = User.from_db(friend_data)
    if not current_user.is_friends_with(friend):
        return {"error": "Can only message friends"}, 403

    msgs = list(mongo.messages.find({
        "$or": [
            {"sender_id": current_user._id, "recipient_id": friend._id},
            {"sender_id": friend._id, "recipient_id": current_user._id}
        ]
    }).sort("created_at", 1))

    

    # convert ObjectIds
    for msg in msgs:
        msg["sender_id"] = str(msg["sender_id"])
        msg["recipient_id"] = str(msg["recipient_id"])
        msg["created_at"] = msg["created_at"].isoformat()
        msg["read"] = msg.get("read", False)

    return stringify_object_ids(msgs), 200

@profile_bp.route("/api/messages/", methods=["GET"])
@login_required
def api_get_messages():
    # optional: filter by recipient
    recipient_id = request.args.get("recipient_id")
    query = {"$or": [{"sender_id": current_user._id}, {"recipient_id": current_user._id}]}

    if recipient_id:
        try:
            recipient_oid = ObjectId(recipient_id)
            query = {"$or": [
                {"sender_id": current_user._id, "recipient_id": recipient_oid},
                {"sender_id": recipient_oid, "recipient_id": current_user._id}
            ]}
        except Exception:
            return {"error": "Invalid recipient id"}, 400

    msgs = list(mongo.messages.find(query).sort("created_at", -1))
    
    # Optional: mark messages sent to me as read
    for msg in msgs:
        if msg.get("recipient_id") == current_user._id and not msg.get("read", False):
            mongo.messages.update_one({"_id": msg["_id"]}, {"$set": {"read": True}})
            msg["read"] = True
    
    # convert ObjectId to string for frontend
    for msg in msgs:
        msg["sender_id"] = str(msg["sender_id"])
        msg["recipient_id"] = str(msg["recipient_id"])
        msg["created_at"] = msg["created_at"].isoformat()
        msg["read"] = msg.get("read", False)

    return msgs, 200


# Send message
@profile_bp.route("/api/messages/send/", methods=["POST"])
@login_required
def send_message():
    data = request.json
    recipient_name = data.get("recipient")
    content = data.get("content", "").strip()

    if not recipient_name or not content:
        return {"error": "Recipient and content required"}, 400

    recipient = User.from_db(mongo.users.find_one({"username": recipient_name}))
    if not recipient:
        return {"error": "Recipient not found"}, 404

    message = {
        "sender_id": current_user._id,
        "recipient_id": recipient._id,
        "content": content,
        "created_at": datetime.utcnow(),
        "read": False
    }
    mongo.messages.insert_one(message)
    return {"success": True}, 200

# Mark message as read
@profile_bp.route("/api/messages/read/", methods=["POST"])
@login_required
def mark_read():
    message_id = request.json.get("message_id")
    if not message_id:
        return {"error": "Message ID required"}, 400

    mongo.messages.update_one(
        {"_id": ObjectId(message_id), "recipient_id": current_user._id},
        {"$set": {"read": True}}
    )
    return {"success": True}, 200
