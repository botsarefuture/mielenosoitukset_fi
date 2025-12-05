from copy import deepcopy
from flask import current_app, jsonify, redirect, request, Blueprint, url_for
from bson.objectid import ObjectId
from datetime import datetime
from flask_caching import Cache
from flask_cors import CORS
from functools import wraps

from flask_login import current_user, login_required

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.classes import Demonstration
from mielenosoitukset_fi.utils.database import stringify_object_ids
from mielenosoitukset_fi.utils.analytics import get_prepped_data
from mielenosoitukset_fi.utils.tokens import (
    TOKENS_COLLECTION,
    TOKEN_USAGE_LOGS,
    token_expired,
    token_renewal_needed,
    create_token,
    check_token
)
from mielenosoitukset_fi.api.exceptions import ApiException, Message
from mielenosoitukset_fi.utils.cache import cache

mongo = DatabaseManager().get_instance().get_db()
api_bp = Blueprint("api", __name__)
CORS(api_bp, resources={r"/*": {"origins": "*"}})


demo_attending_collection = mongo["demo_attending"]
demo_invites_collection = mongo["demo_invites"]
# -------------------------
# ERROR HANDLER
# -------------------------
@api_bp.errorhandler(ApiException)
def handle_api_exception(error):
    return error.message.to_dict(), error.status_code

# -------------------------
# TOKEN DECORATOR
# -------------------------
from flask import make_response

# -------------------------
# TOKEN DECORATOR (updated)
# -------------------------
def token_required(required_scopes=None, auto_renew=True):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                raise ApiException(Message("Missing token", "token_missing"), 401)

            token = auth_header.split(" ", 1)[1] if auth_header.startswith("Bearer ") else auth_header
            token_record = check_token(token)

            # Auto-renew short-lived tokens if needed
            if auto_renew and token_record.get("type") == "short" and token_renewal_needed(token_record):
                new_token, new_expiry = create_token(
                    user_id=token_record.get("user_id"),
                    token_type="short",
                    scopes=token_record.get("scopes"),
                    system=token_record.get("system", False)
                )
                token_record["token"] = new_token
                token_record["expires_at"] = new_expiry

            # Check required scopes
            if required_scopes:
                token_scopes = token_record.get("scopes", [])
                if not any(scope in token_scopes for scope in required_scopes):
                    raise ApiException(Message("Insufficient token scope", "token_scope"), 403)

            # Log usage
            TOKEN_USAGE_LOGS.insert_one({
                "token_id": token_record["_id"],
                "timestamp": datetime.now(),
                "endpoint": request.path,
                "method": request.method,
                "ip": request.remote_addr
            })

            # Attach token record to request
            request.token_record = token_record

            # Execute endpoint
            result = f(*args, **kwargs)

            # Wrap in response to add headers
            if isinstance(result, tuple):
                data, status = result
            else:
                data, status = result, 200

            response = make_response(data, status)
            # Token expiry header
            response.headers["Expires"] = token_record["expires_at"].isoformat()
            # Should renew header (True/False)
            response.headers["X-Token-Should-Renew"] = str(token_renewal_needed(token_record))

            return response
        return decorated
    return decorator

# -------------------------
# HELPER: UPDATE LIKES
# -------------------------
def _update_likes(demo_id, delta=1):
    demo = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
    if not demo:
        raise ApiException(Message("Demonstration not found", "demo_not_found"), 404)
    
    mongo.demo_likes.update_one(
        {"demo_id": ObjectId(demo_id)},
        {"$inc": {"likes": delta}},
        upsert=True
    )
    
    likes_doc = mongo.demo_likes.find_one({"demo_id": ObjectId(demo_id)})
    return likes_doc.get("likes", 0) if likes_doc else 0

# -------------------------
# DEMONSTRATIONS
# -------------------------
from urllib.parse import urlencode

import hashlib
import json
from flask import request

def make_cache_key():
    params = request.args.to_dict(flat=True)
    # sort keys to make order irrelevant
    params_str = json.dumps(params, sort_keys=True)
    return "demonstrations:" + hashlib.md5(params_str.encode("utf-8")).hexdigest()


@api_bp.route("/demonstrations", methods=["GET"])
# @token_required(required_scopes=["read"])
def list_demonstrations():
    """
    Retrieve a paginated and filterable list of demonstrations.

    ---
    ### 🔍 Query Parameters

    - **search** (`str`, optional):  
      Free text search within the title (case-insensitive).

    - **city** (`str`, optional):  
      Filter by city name (case-insensitive).

    - **title** (`str`, optional):  
      Title substring filter (case-insensitive).

    - **tag** (`str`, optional):  
      Filter by tag (case-insensitive match against the `tags` array).

    - **recurring** (`str`, optional):  
      Not currently applied; reserved for future use.

    - **in_past** (`bool`, optional, default=`false`):  
      Include past demonstrations if set to `"true"`.

    - **parent_id** (`str`, optional):  
      Filter by parent demonstration ID.

    - **organization_id** (`str`, optional):  
      Filter by organizer organization ID.

    - **max_days_till** (`int`, optional):  
      Include only demonstrations within *N* days from today (inclusive).

    - **page** (`int`, optional, default=`1`):  
      Pagination page number.

    - **per_page** (`int`, optional, default=`20`):  
      Number of items per page.

    ---
    ### 🧾 Returns
    JSON response:
    ```json
    {
        "page": 1,
        "per_page": 20,
        "total": 133,
        "total_pages": 7,
        "next_url": "...",
        "prev_url": null,
        "results": [ ... list of demonstration objects ... ]
    }
    ```
    """

    # --- Extract & normalize query parameters ---
    def get_param(name: str, default: str = ""):
        return request.args.get(name, default).strip().casefold()
    cache_key = make_cache_key()

    cached_response = cache.get(cache_key) if cache else None

    if cached_response:
        from copy import deepcopy
        response_to_return = deepcopy(cached_response)
        return jsonify(response_to_return), 200

        
    
    

    search = get_param("search")
    raw_city = request.args.get("city", "").strip()
    city_list = [c.strip().casefold() for c in raw_city.split(",") if c.strip()]
    title = get_param("title")
    tag = get_param("tag")
    recurring = get_param("recurring")
    in_past = get_param("in_past")
    parent_id = request.args.get("parent_id", "").strip()
    organization_id = request.args.get("organization_id", "").strip()
    max_days_till = request.args.get("max_days_till", "").strip()

    # --- Parse IDs safely ---
    def safe_objectid(value: str):
        try:
            return ObjectId(value)
        except Exception:
            return None

    _parent_id = safe_objectid(parent_id)
    _org_id = safe_objectid(organization_id)

    # --- Parse numeric filters ---
    max_days = None
    if max_days_till:
        try:
            max_days = max(int(max_days_till), 0)
        except ValueError:
            pass

    # --- Pagination ---
    try:
        page = max(int(request.args.get("page", 1)), 1)
        per_page = max(int(request.args.get("per_page", 20)), 1)
    except ValueError:
        page, per_page = 1, 20

    # --- Prepare date ranges ---
    from datetime import timedelta
    today = datetime.now().date()
    max_date = today + timedelta(days=max_days) if max_days else None

    # --- Base query ---
    from mielenosoitukset_fi.utils.database import DEMO_FILTER
    query = dict(DEMO_FILTER)  # clone to avoid side effects

    if _parent_id:
        query["parent"] = _parent_id
    if _org_id:
        query["organizers"] = {"$elemMatch": {"organization_id": _org_id}}

    # --- Fetch from DB ---
    demos_cursor = mongo.demonstrations.find(query)
    filtered = []

    for demo in demos_cursor:
        try:
            demo_date = datetime.strptime(demo["date"], "%Y-%m-%d").date()
        except Exception:
            continue  # skip invalid date formats

        # Skip past demos unless explicitly requested
        if demo_date < today and in_past != "true":
            continue

        # Skip demos beyond max_days limit
        if max_date and demo_date > max_date:
            continue

        demo_obj = stringify_object_ids(demo)
        title_text = demo_obj.get("title", "").casefold()
        city_text = demo_obj.get("city", "").casefold()
        tags_text = [t.casefold() for t in demo_obj.get("tags", [])]

        if (
            (not search or search in title_text)
            and (not city_list or city_text in city_list)
            and (not title or title in title_text)
            and (not tag or tag in tags_text)
        ):
            filtered.append(demo_obj)

    # --- Sort chronologically ---
    filtered.sort(key=lambda x: datetime.strptime(x["date"], "%Y-%m-%d"))

    # --- Pagination slicing ---
    total = len(filtered)
    total_pages = max((total + per_page - 1) // per_page, 1)
    start, end = (page - 1) * per_page, page * per_page
    paginated = filtered[start:end]

    # --- Navigation URLs ---
    from urllib.parse import urlencode
    base_params = {k: v for k, v in request.args.items() if k not in ["page", "per_page"]}
    qs = urlencode(base_params)
    def build_url(p):
        params = f"page={p}&per_page={per_page}"
        return f"{request.base_url}?{qs}&{params}" if qs else f"{request.base_url}?{params}"

    next_url = build_url(page + 1) if page < total_pages else None
    prev_url = build_url(page - 1) if page > 1 else None

    from copy import deepcopy

    # --- Response object to cache ---
    response_data = {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "next_url": next_url,
        "prev_url": prev_url,
        "results": paginated,
        "rendered_at": datetime.utcnow().isoformat() + "Z",
        "cached": True  # mark as cached
    }

    # --- Cache the response ---
    cache.set(cache_key, response_data)

    # --- Before returning, make a copy and set cached=False ---
    response_to_return = deepcopy(response_data)
    response_to_return["cached"] = False

    return jsonify(response_to_return), 200



@api_bp.route("/demonstrations/<demo_id>", methods=["GET"])
@token_required(required_scopes=["read"])
def get_demonstration(demo_id):
    demo = mongo.demonstrations.find_one({"_id": ObjectId(demo_id), "approved": True})
    if not demo:
        raise ApiException(Message("Demonstration not found", "demo_not_found"), 404)
    
    demo_obj = Demonstration.from_dict(demo)
    return jsonify(stringify_object_ids(demo_obj.to_dict(json=False))), 200

# -------------------------
# DEMO STATS
# -------------------------
@api_bp.route("/demonstrations/<demo_id>/stats", methods=["GET"])
@token_required(required_scopes=["read"])
def get_demo_stats(demo_id):
    stats = get_prepped_data(ObjectId(demo_id))
    if not stats:
        raise ApiException(Message("Demonstration not found", "demo_not_found"), 404)
    
    likes_doc = mongo.demo_likes.find_one({"demo_id": ObjectId(demo_id)})
    
    return jsonify({
        "demo_id": str(demo_id),
        "views": stats.get("views", 0),
        "likes": likes_doc.get("likes", 0) if likes_doc else 0
    }), 200

# -------------------------
# LIKES
# -------------------------
# require token or valid user session, create a silly constructor


def _token_or_session_required(required_perms=None, required_scopes=None):
    """
    Decorator to require either a valid token or a logged-in user session.

    Parameters
    ----------
    required_scopes : list[str], optional
        Scopes required if using token authentication.

    Usage
    -----
    @_token_or_session_required(required_scopes=["write"])
    def my_endpoint():
        ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth_header = request.headers.get("Authorization")

            if auth_header:
                # Token present: validate using your token_required decorator
                return token_required(required_scopes=required_scopes)(f)(*args, **kwargs)

            # No token: fall back to session check
            if current_user.is_authenticated:
                if required_perms:
                    for perm in required_perms:
                        if not current_user.has_permission(perm):
                            raise ApiException(Message("Insufficient permissions", "insufficient_permissions"), 403)
                return f(*args, **kwargs)

            # Neither token nor session: reject
            raise ApiException(Message("Authentication required", "auth_required"), 401)

        return decorated
    return decorator

@api_bp.route("/demonstrations/<demo_id>/like", methods=["POST"])
@_token_or_session_required(required_scopes=["write"])
def like_demo(demo_id):
    likes = _update_likes(demo_id, delta=1)
    demo_attending(demo_id) # A temporary solution
    return jsonify({"likes": likes}), 200

@api_bp.route("/demonstrations/<demo_id>/attending", methods=["GET", "POST"])
@login_required
def demo_attending(demo_id):
    """
    GET: returns whether current user is attending
    POST: toggles attending status or sets it explicitly
    """
    user_id = ObjectId(current_user.id)
    demo_id = ObjectId(demo_id)

    if request.method == "GET":
        doc = demo_attending_collection.find_one({"user_id": user_id, "demo_id": demo_id})
        return jsonify({"demo_id": str(demo_id), "attending": bool(doc and doc.get("attending", True))})

    if request.method == "POST":
        doc = demo_attending_collection.find_one({"user_id": user_id, "demo_id": demo_id})

        # Check if attending was provided in JSON
        new_status = None
        _json = request.get_json(silent=True) 
        if _json and "attending" in _json:
            new_status = bool(_json["attending"])

        if doc:
            # Toggle if no status provided
            if new_status is None:
                new_status = not doc.get("attending", True)
            demo_attending_collection.update_one(
                {"_id": doc["_id"]},
                {"$set": {"attending": new_status}}
            )
        else:
            # First-time attending
            if new_status is None:
                new_status = True
            demo_attending_collection.insert_one({
                "user_id": user_id,
                "demo_id": demo_id,
                "attending": new_status
            })

        return jsonify({"demo_id": str(demo_id), "attending": new_status})


@api_bp.route("/demonstrations/<demo_id>/unlike", methods=["POST"])
@_token_or_session_required(required_scopes=["write"])
def unlike_demo(demo_id):
    likes = _update_likes(demo_id, delta=-1)
    demo_attending(demo_id) # A temporary solution
        
    return jsonify({"likes": likes}), 200

@api_bp.route("/demonstrations/<demo_id>/likes", methods=["GET"])
def get_likes(demo_id):
    likes_doc = mongo.demo_likes.find_one({"demo_id": ObjectId(demo_id)})
    return jsonify({"likes": likes_doc.get("likes", 0) if likes_doc else 0}), 200

# -------------------------
# UNAPPROVED DEMOS
# -------------------------
@api_bp.route("/demonstrations/unapproved", methods=["GET"])
@token_required(required_scopes=["admin"])
def get_unapproved_demonstrations():
    count = mongo.demonstrations.count_documents({"approved": False, "hide": False})
    return jsonify({"has_unapproved": count > 0}), 200

# -------------------------
# ADMIN DEMO INFO
# -------------------------
@api_bp.route("/admin/demonstrations/<demo_id>", methods=["GET"])
@_token_or_session_required(required_scopes=["admin"], required_perms=["VIEW_DEMO"])
def admin_get_demo_info(demo_id):
    demo = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
    if not demo:
        raise ApiException(Message("Demonstration not found", "demo_not_found"), 404)
    return jsonify(stringify_object_ids(demo)), 200

# -------------------------
# TOKEN RENEWAL
# -------------------------
@api_bp.route("/token/renew", methods=["POST"])
@token_required()
def renew_token():
    token_record = request.token_record
    if not token_renewal_needed(token_record):
        raise ApiException(Message("Token does not need renewal yet", "token_no_renew"), 400)
    
    new_token, expires_at = create_token(
        user_id=token_record.get("user_id"),
        token_type=token_record.get("type"),
        scopes=token_record.get("scopes"),
        system=token_record.get("system", False)
    )
    
    return jsonify({
        "token": new_token,
        "expires_at": expires_at,
        "message": "Token renewed successfully"
    }), 200

# -------------------------
# LONG-LIVED TOKEN CREATION
# -------------------------
@api_bp.route("/token/long_lived", methods=["POST"])
@token_required()
def create_long_lived_token():
    """
    Exchange a valid short-lived token for a long-lived token.
    Only allows short-lived tokens to create long-lived ones.
    """
    token_record = request.token_record

    # Only allow short-lived tokens to create long-lived ones
    if token_record.get("type") != "short":
        raise ApiException(Message("Only short-lived tokens can be exchanged", "invalid_token_type"), 400)

    # Optionally, you can check if the token has expired
    if token_expired(token_record):
        raise ApiException(Message("Short-lived token has expired", "token_expired"), 400)

    # Create long-lived token
    long_token, expires_at = create_token(
        user_id=token_record.get("user_id"),
        token_type="long",
        scopes=token_record.get("scopes"),
        system=token_record.get("system", False)
    )

    return jsonify({
        "token": long_token,
        "expires_at": expires_at,
        "message": "Long-lived token created successfully"
    }), 201



# Dummy example: replace this with your DB or actual logic
FRIENDS_DATA = {
    1: [{"name": "Pekka Testinen", "avatar": "/avatars/pekka.jpg"}],
    2: [],
    3: [{"name": "Liisa Virtanen", "avatar": "/avatars/liisa.jpg"},
        {"name": "Mikko Meikäläinen", "avatar": "/avatars/mikko.jpg"}],
}

def _get_user_friends():
    return [friend.get("user_id") for friend in current_user.friends]
    
        
    
from bson import ObjectId
def _get_attending_per_demo(demoId, user_friends):
    """
    Returns a list of friends attending a given demo, with their name and avatar.
    """
    demoId = ObjectId(demoId) if not isinstance(demoId, ObjectId) else demoId

    # 1️⃣ Get attending docs for this demo & friends
    attending_docs = list(demo_attending_collection.find({
        "demo_id": demoId,
        "user_id": {"$in": user_friends},
        "attending": True
    }))

    if not attending_docs:
        return []

    # 2️⃣ Extract the user_ids
    attend_uid = [doc["user_id"] for doc in attending_docs]

    # 3️⃣ Query users collection for display info
    user_docs = mongo["users"].find({"_id": {"$in": attend_uid}})

    # 4️⃣ Build a dict for fast lookup
    user_info_map = {str(user["_id"]): user for user in user_docs}

    # 5️⃣ Combine attendance + user info
    combined = []
    for doc in attending_docs:
        uid = str(doc["user_id"])
        user = user_info_map.get(uid, {})
        combined.append({
            "user_id": uid,
            "name": user.get("displayname", "Unknown"),
            "avatar": user.get("profile_picture")
        })

    return combined


@api_bp.route("/friends-attending", methods=["POST"])
def friends_attending():
    """
    Expects JSON: { "demo_ids": [1, 2, 3] }
    Returns: { "1": [...friends...], "2": [...], ... }
    """
    data = request.get_json()
    if not data or "demo_ids" not in data:
        return jsonify({"error": "Missing demo_ids"}), 400

    

    demo_ids = data["demo_ids"]
    result = {}
    
    
    friends = _get_user_friends()
    
    #print("Filtering by", friends)

    for demo_id in demo_ids:
        
        # Convert to ObjectId if coming as string
        demo_id = ObjectId(demo_id)
        #print(demo_id)
        friends_attending = _get_attending_per_demo(demoId=demo_id, user_friends=friends)
        #print(friends_attending)
        result[str(demo_id)] = friends_attending

    return jsonify(result)

@api_bp.route("/user/friends/")
def friends():
    return redirect(url_for("users.profile.api_friends_list"))
@api_bp.route("/demonstrations/<demo_id>/invite", methods=["POST"])
@login_required
def invite_friends(demo_id):
    """
    Invite friends to a demo.
    Expects JSON body: { "friend_ids": ["id1", "id2", ...] }
    """
    try:
        user_id = current_user._id  # current logged-in user
        data = request.get_json()
        friend_ids = data.get("friend_ids", [])
        if not friend_ids:
            return jsonify({"error": "No friends provided"}), 400

        demo_obj_id = ObjectId(demo_id)
        demo_doc = mongo.demonstrations.find_one({"_id": demo_obj_id})
        demo_title = demo_doc.get("title", "Demo") if demo_doc else "Demo"

        inserted = []
        for fid in friend_ids:
            # 1. Insert invite if not already there
            existing = demo_invites_collection.find_one({
                "demo_id": demo_obj_id,
                "inviter_id": user_id,
                "friend_id": fid
            })
            if existing:
                continue

            doc = {
                "demo_id": demo_obj_id,
                "inviter_id": user_id,
                "friend_id": fid,
                "created_at": datetime.utcnow()
            }
            demo_invites_collection.insert_one(doc)
            inserted.append(fid)

            # 2. Also create a chat message of type "invitation"
            inviter_user = mongo.users.find_one({"_id": ObjectId(user_id)})
            msg = {
                "sender_id": ObjectId(user_id),
                "recipient_id": ObjectId(fid),
                "type": "invitation",
                "content": None,
                "extra": {
                    "invitation_type": "demonstration",
                    "demo_id": str(demo_obj_id),
                    "demo_title": demo_title,
                    "inviter_name": inviter_user.get("displayname") or inviter_user.get("username"),
                },
                "created_at": datetime.utcnow(),
                "read": False
            }
            msg_id = mongo.messages.insert_one(msg).inserted_id
            msg["_id"] = msg_id

            # 3. Emit to both inviter & invitee via Socket.IO
            from mielenosoitukset_fi.users.BPs.chat_ws import serialize_message
            serialized = serialize_message(msg)
            socketio = current_app.extensions['socketio']
            socketio.emit("new_message", {"message": serialized}, room=str(user_id))
            socketio.emit("new_message", {"message": serialized}, room=str(fid))

        return jsonify({
            "demo_id": demo_id,
            "invited_friends": inserted,
            "message": f"Invited {len(inserted)} friends and sent invitations as messages."
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
