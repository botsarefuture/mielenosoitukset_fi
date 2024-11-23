from database_manager import DatabaseManager
from datetime import datetime

from bson.objectid import ObjectId

from utils.database import stringify_object_ids

db_manager = DatabaseManager().get_instance()
mongo = db_manager.get_db()


def log_demo_view(demo_id, user_id=None, session_id=None):
    """This function logs a demonstration view by inserting a new document into the "views" collection in the database.

    Parameters
    ----------
    demo_id :
        The ObjectId of the demonstration that was viewed.
    user_id :
        The ObjectId of the user who viewed the demonstration. (Default value = None)
    session_id :
        The session ID of the user who viewed the demonstration. (Default value = None)

    Returns
    -------


    """
    view_data = {"demo_id": ObjectId(demo_id), "timestamp": datetime.now()}

    if user_id:
        view_data["user_id"] = user_id
    else:
        view_data["session_id"] = session_id

    mongo.analytics.insert_one(view_data)


def get_demo_views(demo_id=None, json=False):
    """This function retrieves all views of a demonstration from the "views" collection in the database.

    Parameters
    ----------
    demo_id :
        The ObjectId of the demonstration for which views are to be retrieved. (Default value = None)
    json :
        Default value = False)

    Returns
    -------


    """
    if not json:
        if not demo_id:
            return mongo.analytics.find()
        else:
            return mongo.analytics.find({"demo_id": ObjectId(demo_id)})

    else:
        if not demo_id:
            return stringify_object_ids(list(mongo.analytics.find()))
        else:
            return stringify_object_ids(
                list(mongo.analytics.find({"demo_id": ObjectId(demo_id)}))
            )


class DemoViewCount:
    """ """

    def __init__(self, demo_id, count):
        self.id = demo_id
        self.views = count

    def __repr__(self):
        return f"DemoViewCount({self.id}, {self.views})"

    def __str__(self):
        return f"Demo ID: {self.id}, Count: {self.views}"


def count_per_demo(data):
    """

    Parameters
    ----------
    data :


    Returns
    -------


    """
    demo_count = {}
    for view in data:
        demo_id = view.get("demo_id")
        if demo_id in demo_count:
            demo_count[demo_id] += 1
        else:
            demo_count[demo_id] = 1

    demo_count = [
        DemoViewCount(demo_id, count) for demo_id, count in demo_count.items()
    ]
    return demo_count


# Could we somehow "prep" reports?
# So that we would do the count_per_demo like every 15 minutes, and save to prepped_analytics collection
# Then we could just fetch the prepped data instead of doing the count every time

# We could also have a "last_updated" field in the prepped_analytics collection
# And only update the data if the last_updated field is older than 15 minutes
# This way we would only update the data every 15 minutes
# And we could still fetch the data every time the report


def prep():
    """This function prepares the analytics data for reporting by counting the number of views per demonstration
    and saving the data to the "prepped_analytics" collection in the database.

    Parameters
    ----------

    Returns
    -------


    """
    data = get_demo_views()
    demo_count = count_per_demo(data)

    prepped_data = [
        {"demo_id": ObjectId(demo.id), "views": demo.views} for demo in demo_count
    ]

    mongo.prepped_analytics.drop()
    mongo.prepped_analytics.insert_many(prepped_data)


def get_prepped_data(demo_id=None):
    """This function retrieves the prepped analytics data from the "prepped_analytics" collection in the database.

    Parameters
    ----------
    demo_id :
        The ObjectId of the demonstration for which prepped analytics data is to be retrieved. (Default value = None)

    Returns
    -------


    """
    if not demo_id:
        return mongo.prepped_analytics.find()
    else:
        return mongo.prepped_analytics.find_one({"demo_id": ObjectId(demo_id)})


# use apscheduler to run the prep function every 15 minutes
