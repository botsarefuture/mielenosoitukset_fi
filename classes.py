from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from dateutil.relativedelta import relativedelta
from flask import url_for

from database_manager import DatabaseManager
from utils.database import stringify_object_ids

DB = DatabaseManager().get_instance().get_db()


class RepeatSchedule:
    def __init__(
        self, frequency: str, interval: int, weekday: Optional[datetime] = None
    ):
        self.frequency = frequency
        self.interval = interval
        self.weekday = weekday

    def __str__(self) -> str:
        frequency_map = {
            "daily": "daily",
            "weekly": "weekly",
            "monthly": "monthly",
            "yearly": "yearly",
        }

        weekday_str = (
            f" on {self.weekday.strftime('%A') if isinstance(self.weekday, datetime) else ''}"
            if self.frequency == "weekly" and self.weekday
            else ""
        )
        return (
            f"every {self.interval} {frequency_map.get(self.frequency, 'unknown')}s{weekday_str}"
            if self.interval > 1
            else frequency_map.get(self.frequency, "unknown") + weekday_str
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frequency": self.frequency,
            "interval": self.interval,
            "weekday": self.weekday,
            "as_string": str(self),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RepeatSchedule":
        return cls(
            frequency=data["frequency"],
            interval=data["interval"],
            weekday=data.get("weekday"),
        )


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
    def __init__(
        self,
        name: str = None,
        email: str = None,
        organization_id: ObjectId = None,
        website: str = None,
        url: str = None,
    ):
        self.name = name
        self.email = email
        self.organization_id = organization_id or None
        self.website = website
        self.url = url

        if organization_id:
            self.fetch_organization_details()

    def to_dict(self, json=False):
        data = super().to_dict(json)
        return data

    def fetch_organization_details(self):
        """Fetch the organization details from the database using the organization_id."""
        if not self.organization_id:
            return

        organization = DB["organizations"].find_one({"_id": self.organization_id})

        if organization:
            self.name = organization.get("name")
            self.email = organization.get("email")
            self.website = organization.get("website")
            try:
                self.url = url_for("org", org_id=str(self.organization_id))
            except RuntimeError:
                self.url = f"/org/{self.organization_id}"

    def validate_organization_id(self):
        """Validate the existence of organization_id in the database."""
        if not self.organization_id:
            return False

        return bool(DB["organizations"].find_one({"_id": self.organization_id}))


class Organization(BaseModel):
    def __init__(
        self,
        name: str,
        description: str,
        email: str,
        website: str = "",
        social_media_links: Dict[str, str] = None,
        members: List[Dict[str, Any]] = None,
        verified: bool = False,
        _id=None,
    ):
        self.name = name
        self.description = description
        self.email = email
        self.website = website
        self.social_media_links = social_media_links or {}
        self.members = members or []
        self.verified = verified
        self._id = _id or ObjectId()

    def save(self):
        """Save the organization to MongoDB."""
        DB["organizations"].update_one(
            {"_id": self._id}, {"$set": self.to_dict()}, upsert=True
        )

    @classmethod
    def from_dict(cls, data: dict):
        """Create an Organization instance from a dictionary."""
        # Remove any deprecated or unnecessary keys
        data.pop("social_medias", None)  # Remove 'social_medias' if it exists
        return cls(**data)
    
class Demonstration(BaseModel):
    """
    A class to represent a demonstration event.

    Attributes:
        title (str): The title of the demonstration.
        date (str): The date of the demonstration.
        start_time (str): The start time of the demonstration.
        end_time (str): The end time of the demonstration.
        facebook (str): The Facebook link for the demonstration.
        city (str): The city where the demonstration is held.
        address (str): The address of the demonstration.
        route (str): The route of the demonstration if it is a march.
        organizers (list): A list of organizers for the demonstration.
        approved (bool): Approval status of the demonstration.
        linked_organizations (dict): Linked organizations for the demonstration.
        img: Image associated with the demonstration.
        _id: The unique identifier for the demonstration.
        description (str): Description of the demonstration.
        tags (list): Tags associated with the demonstration.
        parent (ObjectId): Parent demonstration ID if it is a recurring event.
        created_datetime: The datetime when the demonstration was created.
        recurring (bool): Whether the demonstration is recurring.
        topic (str): The topic of the demonstration.
        type (str): The type of the demonstration.
        repeat_schedule (RepeatSchedule): The repeat schedule for recurring demonstrations.
        repeating (bool): Whether the demonstration is repeating.
        latitude (str): Latitude of the demonstration location.
        longitude (str): Longitude of the demonstration location.
        event_type: The type of event.
        save_flag (bool): Flag to indicate if the demonstration should be saved.
        hide (bool): Flag to indicate if the demonstration should be hidden.

    Methods:
        __init__: Initializes the Demonstration instance.
        merge(id_of_other_demo): Merges another demonstration into this one.
        to_dict(json=False): Converts the instance to a dictionary.
        validate_fields(title, date, start_time, city, address): Validates required fields.
        save(): Saves or updates the demonstration in the database.
    """
    
    def __init__(
        self,
        title: str,
        date: str,
        start_time: str,
        end_time: str,
        facebook: str,
        city: str,
        address: str,
        route: str,
        organizers: list = None,
        approved: bool = False,
        linked_organizations: dict = None,
        img=None,
        _id=None,
        description: str = None,
        tags: list = None,
        parent: ObjectId = None,
        created_datetime=None,
        recurring: bool = False,
        topic: str = None,
        type: str = None,
        repeat_schedule: RepeatSchedule = None,
        repeating: bool = False,
        latitude: str = None,
        longitude: str = None,
        event_type=None,
        save_flag=False,
        hide=False,
    ):
        """
        Initialize a new demonstration event.

        Args:
            title (str): The title of the event.
            date (str): The date of the event.
            start_time (str): The start time of the event.
            end_time (str): The end time of the event.
            facebook (str): The Facebook link for the event.
            city (str): The city where the event is held.
            address (str): The address of the event.
            route (str): The route of the event if it is a march.
            organizers (list, optional): A list of organizers. Defaults to None.
            approved (bool, optional): Whether the event is approved. Defaults to False.
            linked_organizations (dict, optional): Linked organizations. Defaults to None.
            img (optional): Image associated with the event. Defaults to None.
            _id (optional): The unique identifier for the event. Defaults to None.
            description (str, optional): Description of the event. Defaults to None.
            tags (list, optional): Tags associated with the event. Defaults to None.
            parent (ObjectId, optional): Parent event ID for recurring events. Defaults to None.
            created_datetime (optional): The datetime when the event was created. Defaults to None.
            recurring (bool, optional): Whether the event is recurring. Defaults to False.
            topic (str, optional): The topic of the event. Deprecated. Defaults to None.
            type (str, optional): The type of the event. Defaults to None.
            repeat_schedule (RepeatSchedule, optional): The repeat schedule for recurring events. Defaults to None.
            repeating (bool, optional): Whether the event is repeating. Defaults to False.
            latitude (str, optional): Latitude of the event location. Defaults to None.
            longitude (str, optional): Longitude of the event location. Defaults to None.
            event_type (optional): The type of the event. Defaults to None.
            save_flag (bool, optional): Flag to save the event. Defaults to False.
            hide (bool, optional): Flag to hide the event. Defaults to False.
        """

        self.save_flag = save_flag

        self.hide = hide

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
        self.route = route  # If the demonstration is a march, this handles the route

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
        self.repeat_schedule = repeat_schedule
        self.repeating = repeating
        self.recurring = recurring
        if not self.repeating:
            self.repeating = recurring

        elif not self.recurring:
            self.recurring = repeating

        # DEPRECATED
        self.topic = topic or None # Deprecated

        if len(self.tags) == 0 and isinstance(self.topic, str):
            self.tags.append(topic.lower())  # Temporary fix for tags
            self.topic = None # Remove topic
            self.save_flag = True # Save the demonstration to update the tags
            # TODO: #190 Remove this after all demonstrations have been updated
            # with the correct tags

        # Initialize organizers
        self.organizers = [
            Organizer.from_dict(org) if isinstance(org, dict) else org
            for org in (organizers or [])
        ]

        if self.save_flag: # Save the demonstration if the save_flag is set
            self.save() # Save the demonstration

        self.validate_fields(title, date, start_time, city, address) # Validate required fields

    def merge(self, id_of_other_demo):
        """
        Merge another demonstration into this one.

        This method takes the ID of another demonstration, retrieves it from the database,
        and merges its non-None fields into the current demonstration instance. The merged
        demonstration is then saved, and the database is updated to reflect that the other
        demonstration has been merged into this one.

        Args:
            id_of_other_demo (str): The ID of the demonstration to merge into this one.

        Raises:
            ValueError: If the demonstration with the given ID is not found in the database.
        """
        other_demo = DB["demonstrations"].find_one({"_id": ObjectId(id_of_other_demo)})
        if not other_demo:
            raise ValueError(f"Demonstration with id {id_of_other_demo} not found.")

        # Update fields with non-None values from the other demonstration
        for key, value in other_demo.items():
            if key != "_id" and value is not None:
                setattr(self, key, value)

        # Save the merged demonstration
        self.save()

        # Ensure the merged demonstration can be found by both IDs
        DB["demonstrations"].update_one(
            {"_id": ObjectId(id_of_other_demo)}, {"$set": {"merged_into": self._id}}
        )

    def to_dict(self, json=False):
        """
        Convert instance to dictionary, including organizers as dictionaries.

        Args:
            json (bool): If True, convert the instance to a JSON-compatible dictionary.

        Returns:
            dict: A dictionary representation of the instance, with organizers also converted to dictionaries.
        """

        data = super().to_dict(json=json)
        data["organizers"] = [
            org.to_dict(json=json) if isinstance(org, Organizer) else org
            for org in self.organizers
        ]
        return data

    def validate_fields(self, title, date, start_time, city, address):
        """
        Validates that all required fields are provided.

        Args:
            title (str): The title of the event.
            date (str): The date of the event.
            start_time (str): The start time of the event.
            city (str): The city where the event is held.
            address (str): The address where the event is held.

        Raises:
            ValueError: If any of the required fields are missing, raises an error
                        with a message indicating which fields are missing.
        """
        
        if not title or not date or not start_time or not city or not address:
            missing_fields = []
            if not title:
                missing_fields.append("title")
            if not date:
                missing_fields.append("date")
            if not start_time:
                missing_fields.append("start_time")
            if not city:
                missing_fields.append("city")
            if not address:
                missing_fields.append("address")

            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

    def save(self):
        """
        Save or update the demonstration in the database.

        This method converts the demonstration object to a dictionary and checks if it 
        already exists in the database. If it does, the existing entry is updated. 
        Otherwise, a new entry is inserted.

        Returns:
            None
        """

        # Get the database instance from DatabaseManager
        data = self.to_dict()  # Convert the object to a dictionary

        # Check if the demonstration already exists in the database
        if DB["demonstrations"].find_one({"_id": self._id}):
            # Update existing entry
            result = DB["demonstrations"].replace_one({"_id": self._id}, data)
            if result.modified_count:
                print("Demonstration updated successfully.") # TODO: #191 Use utils.logger instead of print
            else:
                print("No changes were made to the demonstration.") # TODO: #191 Use utils.logger instead of print
        else:
            # Insert new entry
            DB["demonstrations"].insert_one(data)
            print("Demonstration saved successfully.") # TODO: #191 Use utils.logger instead of print


class RecurringDemonstration(Demonstration):
    def __init__(
        self,
        title: str,
        date: str,
        start_time: str,
        end_time: str,
        facebook: str,
        city: str,
        address: str,
        route: str,
        organizers: list = None,
        approved: bool = False,
        linked_organizations: dict = None,
        img=None,
        _id=None,
        description: str = None,
        tags: list = None,
        parent: ObjectId = None,
        created_datetime=None,
        recurring: bool = False,
        topic: str = None,
        type: str = None,
        repeat_schedule: RepeatSchedule = None,
        repeating: bool = False,
        latitude: str = None,
        longitude: str = None,
        event_type=None,
        save_flag=False,
        hide=False,
        created_until: Optional[datetime] = None,
    ):

        super().__init__(
            title,
            date,
            start_time,
            end_time,
            facebook,
            city,
            address,
            route,
            organizers,
            approved,
            linked_organizations,
            img,
            _id,
            description,
            tags,
            parent,
            created_datetime,
            recurring=True,
            topic=topic,
            type=type,
            repeat_schedule=repeat_schedule,
            repeating=repeating,
            latitude=latitude,
            longitude=longitude,
            event_type=event_type,
            save_flag=save_flag,
            hide=hide,
        )

        # Set created_until to now if not provided
        self.created_until = created_until or datetime.now()
        self.repeat_schedule = repeat_schedule

    def calculate_next_dates(self) -> List[datetime]:
        """
        Calculate the next demonstration dates based on the frequency and interval.

        This method calculates the upcoming demonstration dates starting from the initial
        date (`self.date`) and continues until one year from the current date. The calculation
        is based on the frequency and interval specified in `self.repeat_schedule`.

        Returns:
            List[datetime]: A list of datetime objects representing the next demonstration dates.
        """

        next_dates = []
        demo_date = datetime.strptime(self.date, "%Y-%m-%d")
        end_date = datetime.now() + relativedelta(years=1)

        while demo_date <= end_date:
            if demo_date > (self.created_until or datetime.now()):
                next_dates.append(demo_date)

            # Calculate next demonstration date based on frequency
            if self.repeat_schedule:
                if self.repeat_schedule.frequency == "daily":
                    demo_date += relativedelta(days=self.repeat_schedule.interval)
                elif self.repeat_schedule.frequency == "weekly":
                    demo_date += relativedelta(weeks=self.repeat_schedule.interval)
                    if self.repeat_schedule.weekday:
                        demo_date += relativedelta(
                            days=(
                                self.repeat_schedule.weekday.weekday()
                                - demo_date.weekday()
                                + 7
                            )
                            % 7
                        )
                elif self.repeat_schedule.frequency == "monthly":
                    demo_date += relativedelta(months=self.repeat_schedule.interval)
                elif self.repeat_schedule.frequency == "yearly":
                    demo_date += relativedelta(years=self.repeat_schedule.interval)

        return next_dates

    def update_demo(self, **kwargs) -> None:
        """
        Update demonstration details using keyword arguments.

        This method allows updating the attributes of the demonstration instance
        by passing keyword arguments. Only the attributes with non-None values
        will be updated.

        Args:
            **kwargs: Arbitrary keyword arguments representing the attributes
                      to be updated and their new values.

        Example:
            demo.update_demo(name="New Name", location="New Location")

        Note:
            If a keyword argument has a value of None, the corresponding attribute
            will not be updated.
        """

        for attr, value in kwargs.items():
            if value is not None:
                setattr(self, attr, value)

    def to_dict(self, json=False) -> Dict[str, Any]:
        """
        Convert the object to a dictionary for easy storage in a database.

        Args:
            json (bool): If True, the dictionary will be JSON serializable.

        Returns:
            Dict[str, Any]: A dictionary representation of the object.

        Notes:
            - Calls the parent class's to_dict method to get the base dictionary.
            - Converts `repeat_schedule` to a dictionary if it is not None.
            - Formats `created_until` as a string in the format "%d.%m.%Y" if it is a datetime object.
        """

        data = super().to_dict(json=json)  # Call the parent to_dict
        if isinstance(self.repeat_schedule, dict):
            self.repeat_schedule = RepeatSchedule.from_dict(self.repeat_schedule)
        data["repeat_schedule"] = (
            self.repeat_schedule.to_dict() if self.repeat_schedule else None
        )
        if self.created_until:
            if isinstance(self.created_until, datetime):
                data["created_until"] = self.created_until.strftime("%d.%m.%Y")
            else:
                # Transform this to datetime object, and then make the strftime call
                data["created_until"] = (
                    datetime.strptime(data["created_until"], "%d.%m.%Y").strftime(
                        "%d.%m.%Y"
                    )
                    if self.created_until is not None
                    else None
                )
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecurringDemonstration":
        """
        Create an instance of RecurringDemonstration from a dictionary.

        Args:
            data (Dict[str, Any]): A dictionary containing the data to create the instance.

        Returns:
            RecurringDemonstration: An instance of the RecurringDemonstration class.

        The dictionary should have the following keys:
            - title (str): The title of the demonstration.
            - date (str): The date of the demonstration.
            - start_time (str): The start time of the demonstration.
            - end_time (str): The end time of the demonstration.
            - facebook (str): The Facebook event link.
            - city (str): The city where the demonstration will take place.
            - address (str): The address of the demonstration.
            - route (str): The route of the demonstration.
            - organizers (list, optional): A list of organizers. Defaults to an empty list.
            - linked_organizations (dict, optional): A dictionary of linked organizations. Defaults to an empty dictionary.
            - repeat_schedule (dict, optional): A dictionary representing the repeat schedule. Defaults to None.
            - created_until (str, optional): The date until which the demonstration is created. Defaults to the current date.
            - _id (str, optional): The unique identifier of the demonstration. Defaults to None.
            - description (str, optional): A description of the demonstration. Defaults to None.
            - tags (list, optional): A list of tags associated with the demonstration. Defaults to an empty list.
        """

        start_time = data["start_time"]
        end_time = data["end_time"]
        created_until = (
            datetime.strptime(data["created_until"], "%d.%m.%Y")
            if data.get("created_until")
            else datetime.now()
        )

        return cls(
            title=data["title"],
            date=data["date"],
            start_time=start_time,
            end_time=end_time,
            facebook=data["facebook"],
            city=data["city"],
            address=data["address"],
            route=data["route"],
            organizers=data.get("organizers", []),
            linked_organizations=data.get("linked_organizations", {}),
            repeat_schedule=(
                RepeatSchedule.from_dict(data["repeat_schedule"])
                if data.get("repeat_schedule")
                else None
            ),
            created_until=created_until,
            _id=data.get("_id"),
            description=data.get("description"),
            tags=data.get("tags", []),
        )

    def __repr__(self) -> str:
        """
        Return a string representation of the RecurringDemonstration instance.

        Returns:
            str: A string containing the title, start time, and end time of the demonstration.
        """
        return f"<RecurringDemonstration(title={self.title}, start_time={self.start_time}, end_time={self.end_time})>"
