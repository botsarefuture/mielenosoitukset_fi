from flask import jsonify, request, Blueprint
from bson.objectid import ObjectId
from datetime import datetime
from flask_cors import CORS
from functools import wraps

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

mongo = DatabaseManager().get_instance().get_db()
api_bp = Blueprint("api", __name__)
CORS(api_bp, resources={r"/*": {"origins": "*"}})

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
@api_bp.route("/demonstrations", methods=["GET"])
@token_required(required_scopes=["read"])
def list_demonstrations():
    search = request.args.get("search", "").lower()
    city = request.args.get("city", "").lower()
    title = request.args.get("title", "").lower()
    tag = request.args.get("tag", "").lower()
    recurring = request.args.get("recurring", "").lower()
    in_past = request.args.get("in_past", "").lower()
    
    today = datetime.now()
    demos_cursor = mongo.demonstrations.find({"approved": True, "hide": False})
    
    result = []
    for demo in demos_cursor:
        demo_date = datetime.strptime(demo["date"], "%Y-%m-%d")
        if demo_date >= today or in_past == "true":
            demo_obj = stringify_object_ids(demo)
            if (
                (search in demo_obj["title"].lower() or not search) and
                (city in demo_obj["city"].lower() or not city) and
                (title in demo_obj["title"].lower() or not title) and
                (tag in [t.lower() for t in demo_obj.get("tags", [])] or not tag) and
                (not recurring or str(demo_obj.get("recurs")) == recurring)
            ):
                result.append(demo_obj)
    
    result.sort(key=lambda x: datetime.strptime(x["date"], "%Y-%m-%d"))
    return jsonify(result), 200


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
@api_bp.route("/demonstrations/<demo_id>/like", methods=["POST"])
@token_required(required_scopes=["write"])
def like_demo(demo_id):
    likes = _update_likes(demo_id, delta=1)
    return jsonify({"likes": likes}), 200

@api_bp.route("/demonstrations/<demo_id>/unlike", methods=["POST"])
@token_required(required_scopes=["write"])
def unlike_demo(demo_id):
    likes = _update_likes(demo_id, delta=-1)
    return jsonify({"likes": likes}), 200

@api_bp.route("/demonstrations/<demo_id>/likes", methods=["GET"])
@token_required(required_scopes=["read"])
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
@token_required(required_scopes=["admin"])
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
