# chat_ws.py
from flask import Blueprint
from flask_socketio import SocketIO, join_room, emit
from flask_login import current_user
from datetime import datetime
from bson.objectid import ObjectId
from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.users.models import User

# get MongoDB instance
mongo = DatabaseManager().get_instance().get_db()

# blueprint
chat_ws = Blueprint("chat_ws", __name__)

username_cache = {}

def _get_username(uid: ObjectId):
    uid = ObjectId(uid)
    if str(uid) in username_cache:
        return username_cache[str(uid)]
    
    result = mongo["users"].find_one({"_id": uid})
    if result:
        username = result.get("username")
        username_cache[str(uid)] = username
        
        return username
    
    else:
        return None
    
    
    

# --- Helper ---
def serialize_message(msg):
    return {
        "_id": str(msg["_id"]),
        "sender_id": str(msg["sender_id"]),
        "recipient_id": str(msg["recipient_id"]),
        "type": msg.get("type", "chat"),
        "content": msg.get("content"),
        "extra": msg.get("extra", {}),
        "created_at": msg["created_at"].isoformat(),
        "read": msg.get("read", False),
        "sender_username": _get_username(msg["sender_id"])
    }


# --- Socket.IO events ---
def init_socketio(socketio: SocketIO):
    @socketio.on("connect")
    def handle_connect():
        print(f"SocketIO: Client connected: {current_user}")
        if not current_user.is_authenticated:
            emit("error", {"error": "Unauthorized"})
            return False
        print(f"SocketIO: User {current_user.username} connected")
        join_room(str(current_user._id))
        print(f"SocketIO: User {current_user.username} joined room {current_user._id}")
        emit("connected", {"msg": "Connected"})

    @socketio.on("get_friends")
    def handle_get_friends():
        friends_list = []
        for f in getattr(current_user, "friends", []):
            fid = f.get("user_id")
            f_data = mongo.users.find_one({"_id": fid})
            if f_data:
                f_user = User.from_db(f_data)
                friends_list.append({
                    "username": f_user.username,
                    "displayname": f_user.displayname or f_user.username,
                    "profile_picture": f_user.profile_picture,
                    "_id": str(f_user._id)
                })
        emit("friends_list", {"friends": friends_list})
        
    @socketio.on("send_message")
    def handle_send_message(data):
        recipient_username = data.get("recipient")
        msg_type = data.get("type", "chat")  # default chat
        content = data.get("content", "").strip()
        extra = data.get("extra", {})

        if not recipient_username:
            return emit("error", {"error": "Recipient required"})

        recipient_data = mongo.users.find_one({"username": recipient_username})
        if not recipient_data:
            return emit("error", {"error": "Recipient not found"})

        recipient = User.from_db(recipient_data)
        if not current_user.is_friends_with(recipient):
            return emit("error", {"error": "Can only message friends"})

        # Validation depending on type
        if msg_type == "chat" and not content:
            return emit("error", {"error": "Chat message requires content"})
        if msg_type == "invitation" and not extra.get("invitation_type"):
            return emit("error", {"error": "Invitation requires invitation_type"})
        if msg_type == "media" and not extra.get("media_url"):
            return emit("error", {"error": "Media requires media_url"})

        msg = {
            "sender_id": current_user._id,
            "recipient_id": recipient._id,
            "type": msg_type,
            "content": content if msg_type == "chat" else None,
            "extra": extra,
            "created_at": datetime.utcnow(),
            "read": False
        }
        msg_id = mongo.messages.insert_one(msg).inserted_id
        msg["_id"] = msg_id

        serialized = serialize_message(msg)

        emit("new_message", {"message": serialized}, room=str(current_user._id))
        emit("new_message", {"message": serialized}, room=str(recipient._id))


    @socketio.on("mark_read")
    def handle_mark_read(data):
        message_id = data.get("message_id")
        if not message_id:
            return
        msg = mongo.messages.find_one({"_id": ObjectId(message_id), "recipient_id": current_user._id})
        if msg:
            mongo.messages.update_one({"_id": ObjectId(message_id)}, {"$set": {"read": True}})
            emit("message_read", {"message_id": message_id}, room=str(msg["sender_id"]))

    @socketio.on("load_messages")
    def handle_load_messages(data):
        friend_username = data.get("friend_username")
        friend_data = mongo.users.find_one({"username": friend_username})
        if not friend_data:
            return emit("error", {"error": "Friend not found"})

        friend = User.from_db(friend_data)
        if not current_user.is_friends_with(friend):
            return emit("error", {"error": "Can only message friends"})

        msgs = list(mongo.messages.find({
            "$or": [
                {"sender_id": current_user._id, "recipient_id": friend._id},
                {"sender_id": friend._id, "recipient_id": current_user._id}
            ]
        }).sort("created_at", 1))

        serialized = [serialize_message(m) for m in msgs]
        emit("chat_history", {"messages": serialized})
