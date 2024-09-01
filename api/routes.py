from flask import jsonify, request, abort, Blueprint
from bson.objectid import ObjectId
from datetime import datetime
from database_manager import DatabaseManager
import json

mongo = DatabaseManager().get_db()

api_bp = Blueprint('api', __name__)

def stringify_object_ids(data):
    """
    Recursively converts all ObjectId instances in the given data structure to strings.

    :param data: The data structure (dict or list) containing ObjectId instances.
    :return: A new data structure with ObjectId instances converted to strings.
    """
    if isinstance(data, dict):
        return {k: stringify_object_ids(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [stringify_object_ids(item) for item in data]
    elif isinstance(data, ObjectId):
        return str(data)
    elif isinstance(data, str):
        return data
    elif isinstance(data, datetime):
        return data.strftime("%d.%m.%Y")  # Convert datetime to Finnish date format
    else:
        print(data)
        return data

@api_bp.route('/demonstrations', methods=['GET'])
def get_demonstrations():
    search_query = request.args.get('search', '')
    today = datetime.now()

    demonstrations = mongo.demonstrations.find({"approved": True})
    filtered_demonstrations = []

    for demo in demonstrations:
        demo_date = datetime.strptime(demo['date'], "%d.%m.%Y")
        if demo_date >= today:
            demo = stringify_object_ids(demo)  # Convert ObjectId to string here
            if (search_query.lower() in demo['title'].lower() or
                search_query.lower() in demo['city'].lower() or
                search_query.lower() in demo['topic'].lower() or
                search_query.lower() in demo['address'].lower()):
                filtered_demonstrations.append(demo)

    filtered_demonstrations.sort(key=lambda x: datetime.strptime(x['date'], "%d.%m.%Y"))

    return json.dumps(filtered_demonstrations)


@api_bp.route('/demonstration/<demo_id>', methods=['GET'])
def get_demonstration_detail(demo_id):
    demo = mongo.demonstrations.find_one({"_id": ObjectId(demo_id), "approved": True})

    if demo is None:
        abort(404, description="Mielenosoitusta ei löytynyt tai sitä ei ole vielä hyväksytty.")

    return json(stringify_object_ids(demo))

@api_bp.route('/demonstration', methods=['POST'])
def create_demonstration():
    """
    Create a new demonstration and store it in the database.
    """
    data = request.get_json()

    # Validate required fields
    required_fields = ['title', 'date', 'start_time', 'end_time', 'topic', 'city', 'address', 'type']
    if not all(field in data for field in required_fields):
        abort(400, description="Missing required fields.")

    # Create a Demonstration instance
    demonstration = {
        "title": data['title'],
        "date": data['date'],
        "start_time": data['start_time'],
        "end_time": data['end_time'],
        "topic": data['topic'],
        "facebook": data.get('facebook', ''),
        "city": data['city'],
        "address": data['address'],
        "type": data['type'],
        "route": data.get('route', None),
        "organizers": data.get('organizers', []),
        "approved": False
    }

    # Save to MongoDB
    mongo.demonstrations.insert_one(demonstration)

    return jsonify({"message": "Mielenosoitus ilmoitettu onnistuneesti! Tiimimme tarkistaa sen, jonka jälkeen se tulee näkyviin sivustolle."}), 201
