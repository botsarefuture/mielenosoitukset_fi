from database_manager import DatabaseManager
from bson.objectid import ObjectId
from flask import url_for
from recu_classes import *

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
    elif isinstance(data, datetime):
        return data.strftime("%d.%m.%Y")  # Convert datetime to Finnish date format
    else:
        return data


class BaseModel:
    """Mixin class for common methods like `to_dict` and `from_dict`."""

    @classmethod
    def from_dict(cls, data):
        """Create an instance from a dictionary."""
        return cls(**data)
    
    def to_dict(self, json=False):
        """Convert instance to dictionary."""
        data = self.__dict__.copy()
        if json and "_id" in data:
            data["_id"] = str(data["_id"])
        
        if json:
            # Replace None with None-equivalent in JSON format
            data = stringify_object_ids(data)

        return data



class Organizer(BaseModel):
    def __init__(self, name: str = None, email: str = None, organization_id: ObjectId = None, website: str = None, url: str = None):
        self.name = name
        self.email = email
        self.organization_id = organization_id or None
        self.website = website
        self.url = url
        self._db_manager = DatabaseManager().get_instance()

        if organization_id:
            self.fetch_organization_details()

    def to_dict(self, json=False):
        data = super().to_dict(json)
        del data["_db_manager"]
        return data

    def fetch_organization_details(self):
        """Fetch the organization details from the database using the organization_id."""
        if not self.organization_id:
            return
        
        db = self._db_manager.get_db()
        organization = db["organizations"].find_one({"_id": self.organization_id})

        if organization:
            self.name = organization.get("name")
            self.email = organization.get("email")
            self.website = organization.get("website")
            self.url = url_for("org", org_id=str(self.organization_id))

    def validate_organization_id(self):
        """Validate the existence of organization_id in the database."""
        if not self.organization_id:
            return False

        db = self._db_manager.get_db()
        return bool(db["organizations"].find_one({"_id": self.organization_id}))


class Organization(BaseModel):
    def __init__(self, name: str, description: str, website: str = "", social_media: dict = None, 
                 demonstrations: list = None, users: dict = None, _id=None):
        self.name = name
        self.description = description
        self.website = website
        self.social_media = social_media or {}
        self.demonstrations = demonstrations or []
        self.users = users or {}
        self._id = _id or ObjectId()

    def save(self):
        """Save the organization to MongoDB."""
        db = DatabaseManager().get_instance().get_db()
        db["organizations"].update_one({"_id": self._id}, {"$set": self.to_dict()}, upsert=True)


class Demonstration(BaseModel):
    def __init__(self, title: str, date: str, start_time: str, end_time: str, facebook: str,
                 city: str, address: str, route: str, organizers: list = None,
                 approved: bool = False, linked_organizations: dict = None, img=None,
                 _id=None, description: str = None, tags: list = None, parent: ObjectId = None, created_datetime = None, recurring: bool = False, topic: str = None, type: str = None, repeat_schedule: RepeatSchedule = None, repeating: bool = False, latitude: str = None, longitude: str = None, event_type = None, save_flag = False):
        
        self.save_flag = save_flag

        self.title = title
        self.description = description

        self.date = date
        self.start_time = start_time
        self.end_time = end_time

        self.city = city
        self.address = address

        self.latitude = latitude
        self.longitude = longitude

        self.event_type = type or event_type
        self.route = route # If the demonstration is march, this handles the route

        self.img = img

        # EXTERNAL LINKS
        self.facebook = facebook


        self.approved = approved
        self.linked_organizations = linked_organizations or {}
        self._id = _id or ObjectId()
        self.tags = tags or []

        self.created_datetime = created_datetime or None

        # RECURRING DEMO STUFF
        self.parent: ObjectId = parent or None
        self.recurring = recurring
        self.repeat_schedule = repeat_schedule
        self.repeating = repeating
        
        # DEPRACED
        self.topic = topic
        
        if len(self.tags) == 0 and isinstance(self.topic, str):
            self.tags.append(topic.lower()) # Temporary fix for tags
            self.save_flag = True

        # Initialize organizers
        self.organizers = [Organizer.from_dict(org) if isinstance(org, dict) else org for org in (organizers or [])]

        if self.save_flag:
            self.save()
        
        self.validate_fields(title, date, start_time, city, address, event_type=self.event_type)


    def to_dict(self, json=False):
        """Convert instance to dictionary, including organizers as dictionaries."""
        data = super().to_dict(json=json)
        data["organizers"] = [org.to_dict(json=json) if isinstance(org, Organizer) else org for org in self.organizers]
        return data

    def validate_fields(self, title, date, start_time, city, address, event_type):
        """Validate required fields for a Demonstration instance."""
        if not all([title, date, start_time, city, address, event_type]):
            raise ValueError("All required fields must be provided and correctly formatted.")

    def save(self):
        """Save or update the demonstration in the database."""
        # Get the database instance from DatabaseManager
        db = DatabaseManager().get_instance().get_db()
        data = self.to_dict()  # Convert the object to a dictionary

        # Check if the demonstration already exists in the database
        if db["demonstrations"].find_one({"_id": self._id}):
            # Update existing entry
            result = db["demonstrations"].replace_one({"_id": self._id}, data)
            if result.modified_count:
                print("Demonstration updated successfully.")
            else:
                print("No changes were made to the demonstration.")
        else:
            # Insert new entry
            db["demonstrations"].insert_one(data)
            print("Demonstration saved successfully.")