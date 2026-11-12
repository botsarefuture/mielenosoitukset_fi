from mielenosoitukset_fi.database_manager import DatabaseManager
from datetime import datetime, timezone

from bson.objectid import ObjectId
from pymongo import DeleteOne, InsertOne, UpdateOne

from mielenosoitukset_fi.utils.database import stringify_object_ids

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
    # Store timestamps as UTC-aware to keep aggregation stable
    view_data = {"demo_id": ObjectId(demo_id), "timestamp": datetime.now(timezone.utc)}

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


def count_views_per_demo():
    """Count raw view events per demonstration using a server-side aggregation.

    Returns
    -------
    list of dict
        One ``{"demo_id": ObjectId, "views": int}`` entry per demonstration
        that has at least one recorded view.

    Notes
    -----
    Counting inside MongoDB keeps the application from pulling the whole
    ``analytics`` collection into Python: the old ``find()`` cursor returned
    every document (1M+) in 16 MB ``getMore`` batches on a COLLSCAN, which
    showed up as repeated slow queries every time the rollup ran.
    """
    rows = mongo.analytics.aggregate(
        [
            {"$group": {"_id": "$demo_id", "views": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ]
    )
    return [{"demo_id": row["_id"], "views": row["views"]} for row in rows]


def prep():
    """This function prepares the analytics data for reporting by counting the number of views per demonstration
    and saving the data to the "prepped_analytics" collection in the database.

    Unlike the old ``drop()`` + ``insert_many()`` (which rewrote all 28k+ rows
    every 15 minutes), rows are tracked by ``demo_id`` and written in place: a
    ``bulk_write`` only updates rows whose count changed, inserts new demos
    (keyed on ``demo_id``), and deletes rows for demos that no longer have raw
    events. Unchanged counters now touch nothing, so the collection stops
    churning and its read path never sees an empty window during the rewrite.

    Parameters
    ----------
    Returns
    -------


    """
    rows = count_views_per_demo()
    new_counts = {row["demo_id"]: row["views"] for row in rows}

    existing = {
        doc.get("demo_id"): doc
        for doc in mongo.prepped_analytics.find({}, {"_id": 1, "demo_id": 1, "views": 1})
        if doc.get("demo_id") is not None
    }

    ops = []
    for demo_id, views in new_counts.items():
        current = existing.get(demo_id)
        if current is None:
            ops.append(InsertOne({"_id": demo_id, "demo_id": demo_id, "views": views}))
        elif current["views"] != views:
            ops.append(
                UpdateOne({"_id": current["_id"]}, {"$set": {"views": views, "demo_id": demo_id}})
            )

    # Demos that still exist as documents but no longer have raw view events.
    for demo_id in set(existing) - set(new_counts):
        ops.append(DeleteOne({"_id": existing[demo_id]["_id"]}))

    if ops:
        mongo.prepped_analytics.bulk_write(ops, ordered=False)


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
