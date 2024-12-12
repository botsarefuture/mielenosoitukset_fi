class Shift:
    def __init__(self, shift_id, start_time, end_time, role, volunteers):
        self.shift_id = shift_id
        self.start_time = start_time
        self.end_time = end_time
        self.role = role
        self.volunteers = volunteers

    @classmethod
    def from_dict(cls, data):
        return cls(
            data["_id"],
            data["start_time"],
            data["end_time"],
            data["role"],
            data["volunteers"],
        )


class Risk:
    """
    Risk evaluation using colors.

    Parameters
    ----------
    color : str
        The color representing the risk level.
    description : str
        The description of the risk.
    """

    def __init__(self, color, description):
        self.color = color or "YELLOW"
        self.description = description or "UNKNOWN"

    @classmethod
    def from_dict(cls, data):
        return cls(data["color"], data["description"])


class Role:
    """
    Role within an action.

    Parameters
    ----------
    name : str
        The name of the role.
    description : str
        The description of the role.
    risk : dict, optional
        The risk associated with the role.
    """

    def __init__(
        self, name, description, risk=None, persons_needed=1, persons_assigned=1
    ):
        self.name = name
        self.description = description
        self.risk = Risk.from_dict(risk) if risk else Risk(None, None)
        self.persons_needed = persons_needed
        self.persons_assigned = persons_assigned
        self.persons_remaining = persons_needed - persons_assigned

    @classmethod
    def from_dict(cls, data):
        return cls(data["name"], data["description"], data.get("risk"))


class Action:
    """
    Action consisting of multiple roles.

    Parameters
    ----------
    action_id : str
        The ID of the action.
    name : str
        The name of the action.
    description : str
        The description of the action.
    roles : list
        The roles associated with the action.
    """

    def __init__(self, action_id, name, description, roles):
        self.action_id = action_id
        self.name = name
        self.description = description
        self.roles = [Role.from_dict(role) for role in roles]

    @classmethod
    def from_dict(cls, data):
        return cls(data["_id"], data["name"], data["description"], data["roles"])


"""
Example data:
{
    "_id": "5f7f6a6c0b8a8b1d9c5b4c2b",
    "name": "Action 1",
    "description": "Description of action 1",
    "roles": [
        {
            "_id": "5f7f6a6c0b8a8b1d9c5b4c2c",
            "name": "Role 1",
            "description": "Description of role 1"
        },
        {
            "_id": "5f7f6a6c0b8a8b1d9c5b4c2d",
            "name": "Role 2",
            "description": "Description of role 2"
        }
    ]
}
"""
