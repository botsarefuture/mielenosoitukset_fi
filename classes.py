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
        self.topic = topic

        if len(self.tags) == 0 and isinstance(self.topic, str):
            self.tags.append(topic.lower())  # Temporary fix for tags
            self.save_flag = True

        # Initialize organizers
        self.organizers = [
            Organizer.from_dict(org) if isinstance(org, dict) else org
            for org in (organizers or [])
        ]

        if self.save_flag:
            self.save()

        self.validate_fields(title, date, start_time, city, address)

    def merge(self, id_of_other_demo):
        """Merge another demonstration into this one."""
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
        """Convert instance to dictionary, including organizers as dictionaries."""
        data = super().to_dict(json=json)
        data["organizers"] = [
            org.to_dict(json=json) if isinstance(org, Organizer) else org
            for org in self.organizers
        ]
        return data

    def validate_fields(self, title, date, start_time, city, address):
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
        """Save or update the demonstration in the database."""
        # Get the database instance from DatabaseManager
        data = self.to_dict()  # Convert the object to a dictionary

        # Check if the demonstration already exists in the database
        if DB["demonstrations"].find_one({"_id": self._id}):
            # Update existing entry
            result = DB["demonstrations"].replace_one({"_id": self._id}, data)
            if result.modified_count:
                print("Demonstration updated successfully.")
            else:
                print("No changes were made to the demonstration.")
        else:
            # Insert new entry
            DB["demonstrations"].insert_one(data)
            print("Demonstration saved successfully.")


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
        """Calculate the next demonstration dates based on the frequency and interval."""
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
        """Update demonstration details using keyword arguments."""
        for attr, value in kwargs.items():
            if value is not None:
                setattr(self, attr, value)

    def to_dict(self, json=False) -> Dict[str, Any]:
        """Convert the object to a dictionary for easy storage in a database."""
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
        """Create an instance from a dictionary."""
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
        return f"<RecurringDemonstration(title={self.title}, start_time={self.start_time}, end_time={self.end_time})>"
