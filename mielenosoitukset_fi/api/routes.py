from flask import jsonify, request, Blueprint
from bson.objectid import ObjectId
from datetime import datetime
from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.classes import Demonstration
from mielenosoitukset_fi.utils.database import stringify_object_ids
from mielenosoitukset_fi.utils.analytics import get_prepped_data
from flask_cors import CORS
from mielenosoitukset_fi.api.exceptions import ApiException, BadRequestException, DemoNotFoundException

# Database instance
mongo = DatabaseManager().get_instance().get_db()

# Blueprint and CORS
api_bp = Blueprint("api", __name__)
CORS(api_bp, resources={r"/*": {"origins": "*"}})

# Helper to format JSON responses with custom messages
def format_response(message, code):
    return jsonify({"message": message.message, "code": code}), code

# Custom exception handlers
@api_bp.errorhandler(ApiException)
def api_exception_handler(error):
    return error.message.to_dict(), error.status_code

@api_bp.route("/demonstrations", methods=["GET"])
def get_demonstrations():
    search_query = request.args.get("search", "").lower()
    today = datetime.now()

    demonstrations = mongo.demonstrations.find({"approved": True})
    filtered_demonstrations = []

    for demo in demonstrations:
        demo_date = datetime.strptime(demo["date"], "%d.%m.%Y")
        if demo_date >= today:
            demo = stringify_object_ids(demo)  # Convert ObjectId to string
            if (
                search_query in demo["title"].lower()
                or search_query in demo["city"].lower()
                or search_query in demo["tags"].lower()
                or search_query in demo["address"].lower()
            ):
                filtered_demonstrations.append(demo)

    # Sort by date in ascending order
    filtered_demonstrations.sort(key=lambda x: datetime.strptime(x["date"], "%d.%m.%Y"))

    return jsonify(filtered_demonstrations), 200

@api_bp.route("/demonstration/<demo_id>", methods=["GET"])
def get_demonstration_detail(demo_id):
    demo = mongo.demonstrations.find_one({"_id": ObjectId(demo_id), "approved": True})

    if demo is None:
        raise DemoNotFoundException()

    demo = Demonstration.from_dict(demo)
    return jsonify(stringify_object_ids(demo.to_dict(json=False)))

@api_bp.route("/demo/<demo_id>/like", methods=["POST"])
def like_demo(demo_id):
    demo = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})

    if demo is None:
        raise DemoNotFoundException()

    mongo.demo_likes.update_one(
        {"demo_id": ObjectId(demo_id)}, {"$inc": {"likes": 1}}, upsert=True
    )

    likes = mongo.demo_likes.find_one({"demo_id": ObjectId(demo_id)}).get("likes", 0)
    return jsonify({"likes": likes})

@api_bp.route("/demo/<demo_id>/unlike", methods=["POST"])
def unlike_demo(demo_id):
    demo = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})

    if demo is None:
        raise DemoNotFoundException()

    mongo.demo_likes.update_one(
        {"demo_id": ObjectId(demo_id)}, {"$inc": {"likes": -1}}, upsert=True
    )

    likes = mongo.demo_likes.find_one({"demo_id": ObjectId(demo_id)}).get("likes", 0)
    return jsonify({"likes": likes})

@api_bp.route("/demo/<demo_id>/likes", methods=["GET"])
def get_likes(demo_id):
    demo = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})

    if demo is None:
        raise DemoNotFoundException()

    likes = mongo.demo_likes.find_one({"demo_id": ObjectId(demo_id)})

    return jsonify({"likes": likes.get("likes", 0) if likes else 0})

@api_bp.route("/demo/<demo_id>/stats", methods=["GET"])
def get_demo_stats_route(demo_id):
    stats = get_prepped_data(ObjectId(demo_id))
    return jsonify(stringify_object_ids(stats))

@api_bp.route("/admin/demo/info/<demo_id>", methods=["GET"])
def get_demo_info(demo_id):
    demo = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})

    if demo is None:
        raise DemoNotFoundException()
    
    return jsonify(stringify_object_ids(demo))