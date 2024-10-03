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
            db_manager = DatabaseManager().get_instance()
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
        """Convert the organizer instance to a dictionary."""
        if self.name == "":
            self.fetch_organization_details()
        return {
            "name": self.name,
            "email": self.email,
            "organization_id": self.organization_id,
            "website": self.website,
        }

    @classmethod
    def from_dict(cls, data):
        """Create an Organizer instance from a dictionary."""
        return cls(
            name=data.get("name"),
            email=data.get("email"),
            organization_id=data.get("organization_id"),
            website=data.get("website"),
        )


class Organization:
    def __init__(
        self,
        name: str,
        description: str,
        website: str = None,
        social_media: dict = None,
        demonstrations: list = None,
        users: dict = None,
        _id=None,
    ):
        if _id is None:
            _id = OID()
            _id = ObjectId(str(_id))

        self.name = name
        self.description = description
        self.website = website or ""
        self.social_media = social_media or {}
        self.demonstrations = demonstrations or []
        self.users = users or {}
        self._id = _id

    def save(self):
        """Save the organization to MongoDB."""
        try:
            db_manager = DatabaseManager()
            db = db_manager.get_db()
            org_data = self.to_dict()

            # Upsert organization in the database
            db["organizations"].update_one(
                {"_id": self._id}, {"$set": org_data}, upsert=True
            )
        except Exception as e:
            print(f"Error saving organization: {e}")

    def to_dict(self):
        """Convert the organization instance to a dictionary."""
        return {
            "_id": self._id,
            "name": self.name,
            "description": self.description,
            "website": self.website,
            "social_media": self.social_media,
            "demonstrations": self.demonstrations,
            "users": self.users,
        }

    @classmethod
    def from_dict(cls, data):
        """Create an Organization instance from a dictionary."""
        return cls(
            _id=data.get("_id"),
            name=data["name"],
            description=data["description"],
            website=data.get("website"),
            social_media=data.get("social_media", {}),
            demonstrations=data.get("demonstrations", []),
            users=data.get("users", {}),
        )

    def add_demonstration(self, demonstration):
        """Add a demonstration to the organization's list."""
        self.demonstrations.append(demonstration)
        self.save()  # Automatically save changes

    def add_user(self, user_id, privileges):
        """Add a user to the organization with specified privileges."""
        self.users[user_id] = privileges
        self.save()  # Automatically save changes

    def update_social_media(self, platform, link):
        """Update or add a social media link."""
        self.social_media[platform] = link
        self.save()  # Automatically save changes

    def remove_user(self, user_id):
        """Remove a user from the organization."""
        if user_id in self.users:
            del self.users[user_id]
            self.save()  # Automatically save changes
        else:
            raise ValueError("User not found in the organization.")


DAY_NAME_TO_NUM = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


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
        img=None,
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
        self.img = img

        self.organizers = []
        for organizer in organizers or []:
            if not isinstance(organizer, Organizer):
                self.organizers.append(Organizer.from_dict(organizer))
            else:
                self.organizers.append(organizer)
        self.approved = approved
        self.linked_organizations = linked_organizations or {}
        self._id = _id

    def validate_fields(
        self, title, date, start_time, end_time, topic, city, address, event_type
    ):
        """
        Validate required fields for a Demonstration instance.
        """
        if not all([title, date, start_time, topic, city, address, event_type]):
            raise ValueError(
                "All required fields must be provided and correctly formatted."
            )

    def to_dict(self):
        """Convert the demonstration instance to a dictionary."""
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
            "img": self.img,
        }

    @classmethod
    def from_dict(cls, data):
        """Create a Demonstration instance from a dictionary."""
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
                img=data.get("img"),
            )
        except KeyError as e:
            raise ValueError(f"Missing required field in data: {e}")

    def link_organization(self, organization_id: str, can_edit: bool):
        """Link an organization to the demonstration with edit rights."""
        self.linked_organizations[organization_id] = can_edit

    def can_edit(self, organization_id: str) -> bool:
        """Check if the given organization has edit rights for the demonstration."""
        return self.linked_organizations.get(organization_id, False)

    def update_organization_link(self, organization_id: str, can_edit: bool):
        """Update the edit rights for an organization."""
        if organization_id in self.linked_organizations:
            self.linked_organizations[organization_id] = can_edit
        else:
            raise ValueError("Organization is not linked.")

    def remove_organization_link(self, organization_id: str):
        """Remove the link to an organization."""
        if organization_id in self.linked_organizations:
            del self.linked_organizations[organization_id]
        else:
            raise ValueError("Organization is not linked.")


from recu_classes import RepeatSchedule, RecurringDemonstration
