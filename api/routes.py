from flask import jsonify, request, abort, Blueprint, Response, make_response
from bson.objectid import ObjectId
from datetime import datetime
from database_manager import DatabaseManager
import json
from classes import Demonstration
from utils.database import stringify_object_ids
from utils.analytics import get_demo_views, get_prepped_data

mongo = DatabaseManager().get_instance().get_db()

api_bp = Blueprint("api", __name__)


@api_bp.route("/demonstrations", methods=["GET"])
def get_demonstrations():
    """ """
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

    response = make_response(json.dumps(filtered_demonstrations))
    response.content_type = "application/json"

    return response


@api_bp.route("/demonstration/<demo_id>", methods=["GET"])
def get_demonstration_detail(demo_id):
    """

    Parameters
    ----------
    demo_id :
        

    Returns
    -------

    
    """
    demo = mongo.demonstrations.find_one({"_id": ObjectId(demo_id), "approved": True})

    if demo is None:
        abort(
            404,
            description="Mielenosoitusta ei löytynyt tai sitä ei ole vielä hyväksytty.",
        )
    demo = Demonstration.from_dict(demo)

    return jsonify(stringify_object_ids(demo.to_dict(json=False)))


@api_bp.route("/demonstration", methods=["POST"])
def create_demonstration():
    """Create a new demonstration and store it in the database."""
    data = request.get_json()

    # Validate required fields
    required_fields = [
        "title",
        "date",
        "start_time",
        "end_time",
        "topic",
        "tags",
        "address",
        "type",
    ]
    if not all(field in data for field in required_fields):
        abort(400, description="Missing required fields.")

    # Create a demonstration instance
    demonstration = {
        "title": data["title"],
        "date": data["date"],
        "start_time": data["start_time"],
        "end_time": data["end_time"],
        "topic": data["topic"],
        "facebook": data.get("facebook", ""),
        "city": data["city"],
        "address": data["address"],
        "type": data["type"],
        "route": data.get("route", None),
        "organizers": data.get("organizers", []),
        "approved": False,
    }

    # Save to MongoDB
    mongo.demonstrations.insert_one(demonstration)

    return (
        jsonify(
            {
                "message": "Mielenosoitus ilmoitettu onnistuneesti! Tiimimme tarkistaa sen, jonka jälkeen se tulee näkyviin sivustolle."
            }
        ),
        201,
    )

@api_bp.route("/demo/<demo_id>/like", methods=["POST"])
def like_demo(demo_id):
    """Like a demonstration. Prevent one session from liking more than once, and one ip liking more than twice a week

    Parameters
    ----------
    demo_id :
        

    Returns
    -------

    
    """
    
    demo = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})

    if demo is None:
        abort(404, description="Mielenosoitusta ei löytynyt.")

    mongo.demo_likes.update_one({"demo_id": ObjectId(demo_id)}, {"$inc": {"likes": 1}}, upsert=True)
    
    likes = mongo.demo_likes.find_one({"demo_id": ObjectId(demo_id)})["likes"]
    
    return jsonify({"likes": likes})

@api_bp.route("/demo/<demo_id>/unlike", methods=["POST"])
def unlike_demo(demo_id):
    """unLike a demonstration. Prevent one session from liking more than once, and one ip liking more than twice a week

    Parameters
    ----------
    demo_id :
        

    Returns
    -------

    
    """
    
    demo = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})

    if demo is None:
        abort(404, description="Mielenosoitusta ei löytynyt.")

    mongo.demo_likes.update_one({"demo_id": ObjectId(demo_id)}, {"$inc": {"likes": -1}}, upsert=True)
    
    likes = mongo.demo_likes.find_one({"demo_id": ObjectId(demo_id)})["likes"]
    
    return jsonify({"likes": likes})

@api_bp.route("/demo/<demo_id>/likes", methods=["GET"])
def get_likes(demo_id):
    """Get the number of likes for a demonstration

    Parameters
    ----------
    demo_id :
        

    Returns
    -------

    
    """
    
    demo = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})

    if demo is None:
        abort(404, description="Mielenosoitusta ei löytynyt.")
    
    likes = mongo.demo_likes.find_one({"demo_id": ObjectId(demo_id)})
    
    if likes is None:
        return jsonify({"likes": 0})
    
    return jsonify({"likes": likes["likes"]})

@api_bp.route("/demo/<demo_id>/stats", methods=["GET"])
def get_demo_stats_route(demo_id):
    """Get the statistics for a demonstration

    Parameters
    ----------
    demo_id :
        

    Returns
    -------

    
    """
    
    stats = get_prepped_data(ObjectId(demo_id))
    print(stats)
    return jsonify(stringify_object_ids(stats))

@api_bp.route("/admin/demo/info/<demo_id>", methods=["GET"])
def get_demo_info(demo_id):
    """Get the information for a demonstration

    Parameters
    ----------
    demo_id :
        

    Returns
    -------

    
    """
    
    demo = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
    
    if demo is None:
        abort(404, description="Mielenosoitusta ei löytynyt.")
    
    return jsonify(stringify_object_ids(demo))