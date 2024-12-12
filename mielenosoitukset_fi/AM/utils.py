from mielenosoitukset_fi.utils.database import get_database_manager
from AM.models import Action
from bson.objectid import ObjectId

DB = get_database_manager()
actions_collection = DB["actions"]


def get_action_by_id(action_id):
    """
    Retrieve an action by its ID.

    Parameters
    ----------
    action_id : str
        The ID of the action.

    Returns
    -------
    action : Action
        The action object.
    """
    action = actions_collection.find_one({"_id": ObjectId(action_id)})
    return Action.from_dict(action)
