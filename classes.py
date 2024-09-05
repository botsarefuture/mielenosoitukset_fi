from database_manager import DatabaseManager
from bson.objectid import ObjectId

from obj_creator import ObjectId as OID


class Organizer:
    def __init__(
        self,
        name: str = None,
        email: str = None,
        organization_id: str = None,
        website: str = None,
    ):
        self.name = name
        self.email = email
        self.organization_id = organization_id
        self.website = website

        if organization_id:
            self.fetch_organization_details()

    def fetch_organization_details(self):
        """Fetch the organization details from the database using the organization_id."""
        try:
            db_manager = DatabaseManager()
            db = db_manager.get_db()

            # Fetch organization details
            organization = db["organizations"].find_one(
                {"_id": ObjectId(self.organization_id)}
            )

            if organization:
                self.name = organization.get("name")
                self.email = organization.get("email")
                self.website = organization.get("website")
            else:
                self.name = None
                self.email = None
                self.website = None
        except Exception as e:
            print(f"Error fetching organization details: {e}")
            self.name = None
            self.email = None
            self.website = None

    def to_dict(self):
        return {
            "name": self.name,
            "email": self.email,
            "organization_id": self.organization_id,
            "website": self.website,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data.get("name"),
            email=data.get("email"),
            organization_id=data.get("organization_id"),
            website=data.get("website"),
        )


DAY_NAME_TO_NUM = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


@NotImplementedError
class RepeatingDemonstration:
    def __init__(
        self,
        title: str,
        day_of_week: str,
        start_time: str,
        end_time: str,
        topic: str,
        city: str,
        address: str,
        event_type: str,
        route: str,
        organizers: list[Organizer] = None,
        approved: bool = False,
        linked_organizations: dict = None,
        _id=None,
    ):
        if _id is None:
            _id = OID()
            _id = ObjectId(str(_id))

        if day_of_week not in [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]:
            raise ValueError(
                'The day of week should be one of these ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]'
            )

        self.title = title
        self.day_of_week = DAY_NAME_TO_NUM[day_of_week]
        self.start_time = start_time
        self.end_time = end_time
        self.topic = topic
        self.city = city
        self.address = address
        self.event_type = event_type
        self.route = route
        self.organizers = organizers if organizers is not None else []
        self.approved = approved
        self.linked_organizations = (
            linked_organizations if linked_organizations is not None else {}
        )
        self._id = _id


class Demonstration:
    def __init__(
        self,
        title: str,
        date: str,
        start_time: str,
        end_time: str,
        topic: str,
        facebook: str,
        city: str,
        address: str,
        event_type: str,
        route: str,
        organizers: list[Organizer] = None,
        approved: bool = False,
        linked_organizations: dict = None,
        _id=None,
    ):

        if _id is None:
            _id = OID()
            _id = ObjectId(str(_id))

        # Validation for required fields
        self.validate_fields(
            title, date, start_time, end_time, topic, city, address, event_type
        )

        self.title = title
        self.date = date
        self.start_time = start_time
        self.end_time = end_time
        self.topic = topic
        self.facebook = facebook
        self.city = city
        self.address = address
        self.event_type = event_type
        self.route = route
        self.organizers = organizers if organizers is not None else []
        self.approved = approved
        self.linked_organizations = (
            linked_organizations if linked_organizations is not None else {}
        )
        self._id = _id

    def validate_fields(
        self, title, date, start_time, end_time, topic, city, address, event_type
    ):
        """
        Validate required fields for a Demonstration instance.
        """
        if (
            not title
            or not date
            or not start_time
            or not end_time
            or not topic
            or not city
            or not address
            or not event_type
        ):
            raise ValueError(
                "All required fields must be provided and correctly formatted."
            )

    def to_dict(self):
        return {
            "_id": self._id,
            "title": self.title,
            "date": self.date,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "topic": self.topic,
            "facebook": self.facebook,
            "city": self.city,
            "address": self.address,
            "type": self.event_type,
            "route": self.route,
            "organizers": [organizer.to_dict() for organizer in self.organizers],
            "approved": self.approved,
            "linked_organizations": self.linked_organizations,
        }

    @classmethod
    def from_dict(cls, data):
        try:
            organizers = (
                [Organizer.from_dict(org) for org in data.get("organizers", [])]
                if data.get("organizers")
                else []
            )
            return cls(
                _id=data.get("_id", None),
                title=data["title"],
                date=data["date"],
                start_time=data["start_time"],
                end_time=data["end_time"],
                topic=data["topic"],
                facebook=data.get("facebook"),
                city=data["city"],
                address=data["address"],
                event_type=data["type"],
                route=data.get("route"),
                organizers=organizers,
                approved=data.get("approved", False),
                linked_organizations=data.get("linked_organizations", {}),
            )
        except KeyError as e:
            raise ValueError(f"Missing required field in data: {e}")

    def link_organization(self, organization_id: str, can_edit: bool):
        """
        Link an organization to the demonstration with edit rights.
        """
        self.linked_organizations[organization_id] = can_edit

    def can_edit(self, organization_id: str) -> bool:
        """
        Check if the given organization has edit rights for the demonstration.
        """
        return self.linked_organizations.get(organization_id, False)

    def update_organization_link(self, organization_id: str, can_edit: bool):
        """
        Update the edit rights for an organization.
        """
        if organization_id in self.linked_organizations:
            self.linked_organizations[organization_id] = can_edit
        else:
            raise ValueError("Organization is not linked.")

    def remove_organization_link(self, organization_id: str):
        """
        Remove the link to an organization.
        """
        if organization_id in self.linked_organizations:
            del self.linked_organizations[organization_id]
        else:
            raise ValueError("Organization is not linked.")
