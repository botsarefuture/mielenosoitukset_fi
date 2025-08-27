from flask import Blueprint, current_app, render_template, request, redirect, url_for, abort, jsonify
from flask_login import current_user, login_required
from urllib.parse import urlparse
from bson.objectid import ObjectId
from datetime import datetime

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.database import stringify_object_ids
from mielenosoitukset_fi.utils.flashing import flash_message
from mielenosoitukset_fi.users.models import User
from mielenosoitukset_fi.utils.logger import logger

mongo = DatabaseManager().get_instance().get_db()

profile_bp = Blueprint(
    "profile", __name__, template_folder="/users/profile/", url_prefix="/profile"
)


@profile_bp.route("/")
@profile_bp.route("/<username>")
def profile(username=None):
    """
    Show a user's profile page.

    Parameters
    ----------
    username : str, optional
        The username of the user to display. If None, shows the current user's profile.

    Returns
    -------
    Response
        Rendered profile page or redirect with flash message if user not found.
    """
    if username is None:
        if current_user.is_authenticated:
            username = current_user.username
        else:
            return abort(404)

    user_data = mongo.users.find_one({"username": username})
    if user_data:
        user_obj = User.from_db(user_data)
        return render_template("users/profile/profile.html", user=user_obj)
    else:
        flash_message("Käyttäjäprofiilia ei löytynyt.", "warning")
        return redirect(url_for("index"))


@profile_bp.route("/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    """
    Redirects to the user settings page.

    Returns
    -------
    Response
        Redirect to the settings page.
    """
    return redirect(url_for("users.auth.settings"))


@profile_bp.route("/api/is_following/")
@login_required
def api_is_following():
    """
    Check if the current user is following another user.

    Returns
    -------
    dict
        {"is_following": bool} if successful,
        or error message with HTTP code.
    """
    username = request.args.get("username")
    if not username:
        return {"error": "Username is required"}, 400

    user_data = mongo.users.find_one({"username": username})
    if not user_data:
        return {"error": "User not found"}, 404

    user_obj = User.from_db(user_data)
    is_following = current_user.am_i_following(user_obj)
    return {"is_following": is_following}, 200


@profile_bp.route("/api/is_friends/")
@login_required
def api_is_friends():
    """
    Check friendship and following status with another user.

    Returns
    -------
    dict
        {
            "is_following": bool,
            "is_friends": bool
        } or error message with HTTP code.
    """
    username = request.args.get("username")
    if not username:
        return {"error": "Username is required"}, 400

    user_data = mongo.users.find_one({"username": username})
    if not user_data:
        return {"error": "User not found"}, 404

    user_obj = User.from_db(user_data)
    return {
        "is_following": current_user.am_i_following(user_obj),
        "is_friends": current_user.is_friends_with(user_obj)
    }, 200


@profile_bp.route("/api/follow/", methods=["POST"])
@login_required
def follow_user():
    """
    Follow a user via API.

    Returns
    -------
    dict
        {"success": True, "is_following": True} if successful,
        or error message with HTTP code.
    """
    data = request.json
    username = data.get("username")
    if not username:
        return {"error": "Username required"}, 400

    user_obj = User.from_db(mongo.users.find_one({"username": username}))
    if not user_obj:
        return {"error": "User not found"}, 404

    if current_user.am_i_following(user_obj):
        return {"error": "Already following"}, 400

    current_user.following.append(user_obj.id)
    user_obj.followers.append(current_user.id)
    current_user.save()
    user_obj.save()
    return {"success": True, "is_following": True}, 200


@profile_bp.route("/api/unfollow/", methods=["POST"])
@login_required
def unfollow_user():
    """
    Unfollow a user via API.

    Returns
    -------
    dict
        {"success": True, "is_following": False} if successful,
        or error message with HTTP code.
    """
    data = request.json
    username = data.get("username")
    if not username:
        return {"error": "Username required"}, 400

    user_obj = User.from_db(mongo.users.find_one({"username": username}))
    if not user_obj:
        return {"error": "User not found"}, 404

    if not current_user.am_i_following(user_obj):
        return {"error": "Not following"}, 400

    current_user.following.remove(user_obj.id)
    user_obj.followers.remove(current_user.id)
    current_user.save()
    user_obj.save()
    return {"success": True, "is_following": False}, 200

@profile_bp.route("/api/send_friend_request/", methods=["POST"])
@login_required
def send_friend_request():
    """
    Send a friend request to another user.

    Parameters
    ----------
    username : str, in JSON payload
        The username of the user to send a friend request to.

    Returns
    -------
    dict
        {"success": True, "status": "request_sent"} if successful,
        or error message with HTTP code.
    """
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
    """
    Accept a friend request from another user.

    Parameters
    ----------
    username : str, in JSON payload
        The username of the user whose friend request to accept.

    Returns
    -------
    dict
        {"success": True, "status": "friends"} if successful,
        or error message with HTTP code.
    """
    data = request.json
    username = data.get("username")
    if not username:
        return {"error": "Username required"}, 400

    other_data = mongo.users.find_one({"username": username})
    if not other_data:
        return {"error": "User not found"}, 404

    other = User.from_db(other_data)

    req = next((r for r in current_user.friend_requests if r["sent_by"] == other._id), None)
    if not req:
        return {"error": "No friend request from this user"}, 400

    current_user.friend_requests = [r for r in current_user.friend_requests if r["sent_by"] != other._id]
    current_user.friends.append({"user_id": other._id, "last_updated": datetime.utcnow()})
    other.friends.append({"user_id": current_user._id, "last_updated": datetime.utcnow()})

    current_user.save()
    other.save()
    return {"success": True, "status": "friends"}, 200


@profile_bp.route("/api/reject_friend_request/", methods=["POST"])
@login_required
def reject_friend_request():
    """
    Reject a friend request from another user.

    Parameters
    ----------
    username : str, in JSON payload
        The username of the user whose friend request to reject.

    Returns
    -------
    dict
        {"success": True, "status": "rejected"} if successful,
        or error message with HTTP code.
    """
    data = request.json
    username = data.get("username")
    if not username:
        return {"error": "Username required"}, 400

    other_data = mongo.users.find_one({"username": username})
    if not other_data:
        return {"error": "User not found"}, 404

    other = User.from_db(other_data)

    current_user.friend_requests = [r for r in current_user.friend_requests if r["sent_by"] != other._id]
    current_user.save()
    return {"success": True, "status": "rejected"}, 200


@profile_bp.route("/api/friend_state/")
@login_required
def friend_state():
    """
    Get the friendship state with another user.

    Parameters
    ----------
    username : str, in query parameters
        The username of the other user.

    Returns
    -------
    dict
        {"friend_state": state} where state is one of:
        "friends", "incoming_request", "outgoing_request", or "none",
        or error message with HTTP code.
    """
    username = request.args.get("username")
    if not username:
        return {"error": "Username required"}, 400

    other_data = mongo.users.find_one({"username": username})
    if not other_data:
        return {"error": "User not found"}, 404

    other = User.from_db(other_data)

    if any(f.get("user_id", f) == other._id for f in current_user.friends):
        state = "friends"
    elif any((r.get("sent_by", r) if isinstance(r, dict) else r) == other._id for r in current_user.friend_requests):
        state = "incoming_request"
    elif any((r.get("sent_by", r) if isinstance(r, dict) else r) == current_user._id for r in other.friend_requests):
        state = "outgoing_request"
    else:
        state = "none"

    return {"friend_state": state}, 200


@profile_bp.route("/api/friends_list/", methods=["GET"])
@login_required
def api_friends_list():
    """
    Get a list of all friends for the current user.

    Returns
    -------
    dict
        {"friends": list of dicts with keys:
            "username", "displayname", "profile_picture", "_id"}
    """
    friends = []
    for friend in current_user.friends:
        fid = friend.get("user_id")
        f_data = mongo.users.find_one({"_id": fid})
        if f_data:
            f_user = User.from_db(f_data)
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
    """
    Get count of unread messages from each friend.

    Returns
    -------
    dict
        {"friend_username": unread_count}
    """
    counts = {}
    for f in current_user.friends:
        fid = f.get("user_id")
        msgs = mongo.messages.count_documents({
            "sender_id": fid,
            "recipient_id": current_user._id,
            "read": False
        })
        f_data = mongo.users.find_one({"_id": fid})
        if f_data:
            f_user = User.from_db(f_data)
            counts[f_user.username] = msgs
    return counts, 200


@profile_bp.route("/api/messages/<friend_username>/", methods=["GET"])
@login_required
def api_messages_with(friend_username):
    """
    Get all messages between current user and a specific friend.

    Parameters
    ----------
    friend_username : str
        Username of the friend.

    Returns
    -------
    list of dict
        Each dict has keys: "sender_id", "recipient_id", "content", "created_at", "read",
        or error message with HTTP code.
    """
    friend_data = mongo.users.find_one({"username": friend_username})
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

    for msg in msgs:
        msg["sender_id"] = str(msg["sender_id"])
        msg["recipient_id"] = str(msg["recipient_id"])
        msg["created_at"] = msg["created_at"].isoformat()
        msg["read"] = msg.get("read", False)

    return stringify_object_ids(msgs), 200


@profile_bp.route("/api/messages/", methods=["GET"])
@login_required
def api_get_messages():
    """
    Get all messages for the current user, optionally filtered by recipient.

    Query Parameters
    ----------------
    recipient_id : str, optional
        ObjectId of a recipient to filter messages.

    Returns
    -------
    list of dict
        Each dict has keys: "sender_id", "recipient_id", "content", "created_at", "read",
        or error message with HTTP code.
    """
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

    for msg in msgs:
        if msg.get("recipient_id") == current_user._id and not msg.get("read", False):
            mongo.messages.update_one({"_id": msg["_id"]}, {"$set": {"read": True}})
            msg["read"] = True

    for msg in msgs:
        msg["sender_id"] = str(msg["sender_id"])
        msg["recipient_id"] = str(msg["recipient_id"])
        msg["created_at"] = msg["created_at"].isoformat()
        msg["read"] = msg.get("read", False)

    return msgs, 200


@profile_bp.route("/api/messages/send/", methods=["POST"])
@login_required
def send_message():
    """
    Send a message to a friend.

    Parameters
    ----------
    recipient : str, in JSON payload
        Username of the recipient.
    content : str, in JSON payload
        Message content.

    Returns
    -------
    dict
        {"success": True} if successful,
        or error message with HTTP code.
    """
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


@profile_bp.route("/api/messages/read/", methods=["POST"])
@login_required
def mark_read():
    """
    Mark a message as read.

    Parameters
    ----------
    message_id : str, in JSON payload
        The ObjectId of the message to mark as read.

    Returns
    -------
    dict
        {"success": True} if successful,
        or error message with HTTP code.
    """
    message_id = request.json.get("message_id")
    if not message_id:
        return {"error": "Message ID required"}, 400

    mongo.messages.update_one(
        {"_id": ObjectId(message_id), "recipient_id": current_user._id},
        {"$set": {"read": True}}
    )
    return {"success": True}, 200



# DEPRECATED ROUTES

@profile_bp.route("/follow/<username>", methods=["POST"])
@login_required
def follow(username):
    """
    Deprecated route for following a user.

    .. deprecated:: 4.2.0
       Use the API route `/api/follow/`.

    Parameters
    ----------
    username : str
        The username to follow.

    Returns
    -------
    Response
        Redirect to profile page with warning flash message.
    """
    flash_message(
        "This route is deprecated. Please use the new API: `/api/follow/`.",
        "warning"
    )
    import warnings
    warnings.warn(
        "Route /follow/<username> is deprecated. Use /api/follow/ instead.",
        DeprecationWarning
    )
    referrer = request.referrer or url_for("users.profile.profile", username=username)
    return redirect(referrer)


@profile_bp.route("/unfollow/<username>", methods=["POST"])
@login_required
def unfollow(username):
    """
    Deprecated route for unfollowing a user.

    .. deprecated:: 4.2.0
       Use the API route `/api/unfollow/`.

    Parameters
    ----------
    username : str
        The username to unfollow.

    Returns
    -------
    Response
        Redirect to profile page with warning flash message.
    """
    flash_message(
        "This route is deprecated. Please use the new API: `/api/unfollow/`.",
        "warning"
    )
    import warnings
    warnings.warn(
        "Route /unfollow/<username> is deprecated. Use /api/unfollow/ instead.",
        DeprecationWarning
    )
    referrer = request.referrer or url_for("users.profile.profile", username=username)
    return redirect(referrer)
