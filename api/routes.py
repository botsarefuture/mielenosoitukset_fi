from flask import jsonify, request, abort, Blueprint, Response, make_response
from bson.objectid import ObjectId
from datetime import datetime
from database_manager import DatabaseManager
import json
from classes import Demonstration
from utils.database import stringify_object_ids

from utils import DATE_FORMAT

mongo = DatabaseManager().get_instance().get_db()

api_bp = Blueprint("api", __name__)


@api_bp.route("/demonstrations", methods=["GET"])
def get_demonstrations():
    search_query = request.args.get("search", "").lower()
    today = datetime.now()

    demonstrations = mongo.demonstrations.find({"approved": True})
    filtered_demonstrations = []

    for demo in demonstrations:
        demo_date = datetime.strptime(demo["date"], DATE_FORMAT)
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
    filtered_demonstrations.sort(key=lambda x: datetime.strptime(x["date"], DATE_FORMAT))

    response = make_response(json.dumps(filtered_demonstrations))
    response.content_type = "application/json"

    return response


@api_bp.route("/demonstration/<demo_id>", methods=["GET"])
def get_demonstration_detail(demo_id):
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
    """
    Create a new demonstration and store it in the database.
    """
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
