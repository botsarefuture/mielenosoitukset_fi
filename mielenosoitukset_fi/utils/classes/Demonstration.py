from .BaseModel import BaseModel
from .Organizer import Organizer
from mielenosoitukset_fi.utils.database import get_database_manager
from mielenosoitukset_fi.utils.validators import (
    event_type_convertor,
    valid_event_type,
    return_exists,
)
from .RepeatSchedule import RepeatSchedule
from bson import ObjectId
from datetime import datetime  # Added import for datetime


DB = get_database_manager()


class Demonstration(BaseModel):
    # Running number and slug fields for user-friendly URLs
    running_number: int = None
    slug: str = None
    @classmethod
    def from_dict(cls, data):
        """
        Create a Demonstration instance from a dictionary.

        Parameters
        ----------
        data : dict
            Dictionary containing demonstration data.

        Returns
        -------
        Demonstration
            An instance of Demonstration initialized from the dictionary.
        """
        # Helper to get value with fallback
        def get(key, default=None):
            return data.get(key, default)

        return cls(
            title=get("title"),
            date=get("date"),
            start_time=get("start_time"),
            end_time=get("end_time"),
            facebook=get("facebook"),
            city=get("city"),
            address=get("address"),
            route=get("route"),
            organizers=get("organizers"),
            approved=get("approved", False),
            linked_organizations=get("linked_organizations"),
            img=get("img"),
            _id=get("_id"),
            description=get("description"),
            tags=get("tags"),
            parent=get("parent"),
            created_datetime=get("created_datetime"),
            recurring=get("recurring", False),
            topic=get("topic"),
            type=get("type"),
            repeat_schedule=get("repeat_schedule"),
            repeating=get("repeating", False),
            latitude=get("latitude"),
            longitude=get("longitude"),
            event_type=get("event_type"),
            save_flag=get("save_flag", False),
            hide=get("hide", False),
            aliases=get("aliases"),
            in_past=get("in_past", False),
            preview_image=get("preview_image"),
            merged_into=get("merged_into"),
            cover_picture=get("cover_picture"),
            created_until=get("created_until")
        )
    """
    A class to represent a demonstration event.

    This class encapsulates the details of a demonstration event, including its title, date, time, location, organizers, and other relevant information. It provides methods to initialize, validate, and manipulate demonstration events.

    Parameters
    ----------
    title : str
        The title of the event.
    date : str
        The date of the event.
    start_time : str
        The start time of the event.
    end_time : str
        The end time of the event.
    facebook : str
        The Facebook link for the event.
    city : str
        The city where the event is held.
    address : str
        The address of the event.
    route : str
        The route of the event if it is a march.
    organizers : list, optional
        A list of organizers. Defaults to None.
    approved : bool, optional
        Whether the event is approved. Defaults to False.
    linked_organizations : dict, optional
        Linked organizations. Defaults to None.
    img : optional
        Image associated with the event. Defaults to None.
    _id : optional
        The unique identifier for the event. Defaults to None.
    description : str, optional
        Description of the event. Defaults to None.
    tags : list, optional
        Tags associated with the event. Defaults to None.
    parent : ObjectId, optional
        Parent event ID for recurring events. Defaults to None.
    created_datetime : optional
        The datetime when the event was created. Defaults to None.
    recurring : bool, optional
        Whether the event is recurring. Defaults to False.
    topic : str, optional
        The topic of the event. Deprecated. Defaults to None.
    type : str, optional
        The type of the event. Defaults to None.
    repeat_schedule : RepeatSchedule, optional
        The repeat schedule for recurring events. Defaults to None.
    repeating : bool, optional
        Whether the event is repeating. Defaults to False.
    latitude : str, optional
        Latitude of the event location. Defaults to None.
    longitude : str, optional
        Longitude of the event location. Defaults to None.
    event_type : optional
        The type of the event. Defaults to None.
    save_flag : bool, optional
        Flag to save the event. Defaults to False.
    hide : bool, optional
        Flag to hide the event. Defaults to False.
    aliases : list, optional
        Aliases for the event. Defaults to None.
    in_past : bool, optional
        Whether the event is in the past. Defaults to False.
    preview_image : str, optional
        URL of the preview image for the event. Defaults to None.
    merged_into : ObjectId, optional
        ID of the demonstration this one is merged into. Defaults to None.
    cover_picture : str, optional
        URL of the cover picture for the event. Defaults to None.

    Notes
    -----
    .. deprecated:: 1.6.0
        `topic` will be removed in a future version.

    Methods
    -------
    alias_fix()
        Ensures that all aliases are of type ObjectId.
    merge(id_of_other_demo)
        Merge another demonstration into this one.
    update_self_from_recurring(recurring_demo)
        Update the demonstration details using a recurring demonstration.
    to_dict(json=False)
        Convert instance to dictionary, including organizers as dictionaries.
    validate_fields(title, date, start_time, city, address)
        Validates that all required fields are provided.
    save()
        Save or update the demonstration in the database.
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
        aliases=None,
        in_past=False,
        preview_image: str = None,
        merged_into: ObjectId = None,  # Added parameter
        cover_picture: str = None,  # Added field
        created_until = None,
        running_number: int = None,
        slug: str = None
    ):
        """
        Initialize a new demonstration event.

        Parameters
        ----------
        title : str
            The title of the event.
        date : str
            The date of the event.
        start_time : str
            The start time of the event.
        end_time : str
            The end time of the event.
        facebook : str
            The Facebook link for the event.
        city : str
            The city where the event is held.
        address : str
            The address of the event.
        route : str
            The route of the event if it is a march.
        organizers : list, optional
            A list of organizers. Defaults to None.
        approved : bool, optional
            Whether the event is approved. Defaults to False.
        linked_organizations : dict, optional
            Linked organizations. Defaults to None.
        img : optional
            Image associated with the event. Defaults to None.
        _id : optional
            The unique identifier for the event. Defaults to None.
        description : str, optional
            Description of the event. Defaults to None.
        tags : list, optional
            Tags associated with the event. Defaults to None.
        parent : ObjectId, optional
            Parent event ID for recurring events. Defaults to None.
        created_datetime : optional
            The datetime when the event was created. Defaults to None.
        recurring : bool, optional
            Whether the event is recurring. Defaults to False.
        topic : str, optional
            **[Depraced]**
            The topic of the event. Deprecated. Defaults to None.
        type : str, optional
            The type of the event. Defaults to None.
        repeat_schedule : RepeatSchedule, optional
            The repeat schedule for recurring events. Defaults to None.
        repeating : bool, optional
            Whether the event is repeating. Defaults to False.
        latitude : str, optional
            Latitude of the event location. Defaults to None.
        longitude : str, optional
            Longitude of the event location. Defaults to None.
        event_type : optional
            The type of the event. Defaults to None.
        save_flag : bool, optional
            Flag to save the event. Defaults to False.
        hide : bool, optional
            Flag to hide the event. Defaults to False.
        aliases : list, optional
            Aliases for the event. Defaults to None.
        in_past : bool, optional
            Whether the event is in the past. Defaults to False.
        preview_image : str, optional
            URL of the preview image for the event. Defaults to None.
        merged_into : ObjectId, optional
            ID of the demonstration this one is merged into. Defaults to None.
        cover_picture : str, optional
            URL of the cover picture for the event. Defaults to None.

        Notes
        -----
        .. deprecated:: 1.6.0
            `topic` will be removed in a future version.
        """
        # Convert date and time fields to ISO8601 format
        self.date = self._to_iso8601_date(date)
        
        if self.date != date:
            self.save_flag = True
            
        self.start_time = self._to_iso8601_time(start_time)
        if self.start_time != start_time:
            self.save_flag = True
            
        self.end_time = self._to_iso8601_time(end_time)
        if self.end_time != end_time:
            self.save_flag = True

        self.save_flag = save_flag

        self.hide = hide

        self.title = title
        self.description = description

        # Removed direct assignment for date, start_time, end_time

        self.city = city
        self.address = address

        self.latitude = latitude
        self.longitude = longitude

        self.event_type = event_type_convertor(type or event_type)

        if not valid_event_type(self.event_type):
            raise ValueError(f"Invalid event type: {self.event_type}")

        self.route = route  # If the demonstration is a march, this handles the route
        
        if self.route is not None:
            try:
                rou = self.route.split(",")
                if len(rou) > 1:
                    self.route = rou
            except:
                pass


        self.img = img

        # EXTERNAL LINKS
        self.facebook = facebook

        self.approved = approved
        self.linked_organizations = linked_organizations or {}  # What is this used for?
        # TODO: #232 Remove linked_organizations if not used

        self._id = _id or ObjectId()  # Unique ID for the demonstration
        self.running_number = running_number
        self.slug = slug
        self.tags = tags or []  # Tags for the demonstration

        self.created_datetime = created_datetime or None

        # RECURRING DEMO STUFF
        self.parent: ObjectId = parent or None
        self.repeat_schedule = repeat_schedule
        self.repeating, self.recurring = return_exists(repeating, recurring, False)

        # DEPRECATED
        self.topic = topic or None  # Deprecated

        if len(self.tags) == 0 and isinstance(self.topic, str):
            self.tags.append(topic.lower())  # Temporary fix for tags
            self.topic = None  # Remove topic
            self.save_flag = True  # Save the demonstration to update the tags
            # TODO: #190 Remove this after all demonstrations have been updated
            # with the correct tags
        

        # Initialize organizers
        self.organizers = [
            Organizer.from_dict(org) if isinstance(org, dict) else org
            for org in (organizers or [])
        ]

        self.in_past = in_past  # Whether or not in past
        if self.in_past == True:
            self.hide = True
            self.save_flag = True

        self.aliases = aliases or []
        self.alias_fix()

        self.preview_image = preview_image
        
        def build_url(self):
            return '/static/demo_preview/' + str(self._id) + '.png'
    
            
        if self.preview_image is not None and self.preview_image.startswith("/static/demo_preview/"):
            # add https://mielenosoitukset.fi/ to the beginning of the URL
            self.preview_image = "https://mielenosoitukset.fi" + self.preview_image
            self.save_flag = True # Save the demonstration to update the preview image
        
        self.merged_into = merged_into  # Assign new parameter
        self.cover_picture = cover_picture

        if self.save_flag:  # Save the demonstration if the save_flag is set
            self.save()  # Save the demonstration

        self.validate_fields(
            title, date, start_time, city, address
        )  # Validate required fields

    def alias_fix(self):
        """
        Ensures that all aliases are of type ObjectId.

        This method iterates through the `aliases` attribute of the instance and converts any alias that is not already an ObjectId to an ObjectId.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Examples
        --------
        >>> demo = Demonstration(...)
        >>> demo.alias_fix()
        """
        aliases = self.aliases.copy()

        for alias in aliases:
            if not isinstance(alias, ObjectId):
                alias = ObjectId(alias)

        self.aliases = aliases

    def merge(self, id_of_other_demo):
        """
        Merge another demonstration into this one.

        This method takes the ID of another demonstration, retrieves it from the database,
        and merges its non-None fields into the current demonstration instance. The merged
        demonstration is then saved, and the database is updated to reflect that the other
        demonstration has been merged into this one.

        Parameters
        ----------
        id_of_other_demo : str or ObjectId
            The ID of the demonstration to merge into this one.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If the demonstration with the provided ID is not found in the database.

        See Also
        --------
        save : Save the demonstration to the database.

        Examples
        --------
        >>> demo = Demonstration(...)
        >>> demo.merge("60f8e1e7a1b9c9b8f6b3f3b2") # Merge the demonstration with ID "60f8e1e7a1b9c9b8f6b3f3b2" into the current demonstration.
        """
        other_demo_data = DB["demonstrations"].find_one(
            {"_id": ObjectId(id_of_other_demo)}
        )
        if not other_demo_data:
            raise ValueError(f"Demonstration with id {id_of_other_demo} not found.")

        other_demo = Demonstration.from_dict(other_demo_data)

        # Update fields with non-None values from the other demonstration
        for key, value in other_demo.to_dict().items():
            if key != "_id" and value is not None:
                setattr(self, key, value)

        # Save the merged demonstration
        self.save()

        # Ensure the merged demonstration can be found by both IDs
        DB["demonstrations"].update_one(
            {"_id": ObjectId(id_of_other_demo)},
            {"$set": {"merged_into": self._id, "hide": True}},
        )

        self.aliases.append(
            ObjectId(id_of_other_demo)
        )  # Make sure that this gets saved

        self.save()

    def update_self_from_recurring(self, recurring_demo: "RecurringDemonstration"):
        """Update the demonstration details using a recurring demonstration.

        This method updates the demonstration instance with the details from a recurring
        demonstration. The details that are updated include the title, description, tags,
        and organizers.

        Parameters
        ----------
        recurring_demo : RecurringDemonstration
            The recurring demonstration instance.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If the provided demonstration is not a RecurringDemonstration instance.

        See Also
        --------
        RecurringDemonstration : A class representing a recurring demonstration.
        """
        if not isinstance(
            recurring_demo, Demonstration
        ):  # RecurringDemonstration is a subclass of Demonstration, so it will return True
            raise ValueError(
                "The provided demonstration is not a RecurringDemonstration instance."
            )

        self.title = recurring_demo.title
        self.description = recurring_demo.description
        self.tags = recurring_demo.tags
        self.organizers = recurring_demo.organizers

        self.save()

    def to_dict(self, json=False):
        """
        Convert instance to dictionary, including organizers as dictionaries.

        Parameters
        ----------
        json : bool, optional
            If True, convert the instance to a JSON-compatible dictionary. Defaults to False.

        Returns
        -------
        dict
            A dictionary representation of the instance, with organizers and aliases converted appropriately.

        See Also
        --------
        BaseModel.to_dict : Convert the instance to a dictionary.
        """
        data = super().to_dict(json=json)
        data["organizers"] = [
            org.to_dict(json=json) if isinstance(org, Organizer) else org
            for org in self.organizers
        ]
        data["aliases"] = [str(alias) for alias in self.aliases]
        data["preview_image"] = self.preview_image
        data["merged_into"] = str(self.merged_into) if self.merged_into else None  # Added line
        data["running_number"] = self.running_number
        data["slug"] = self.slug
        return data

    def validate_fields(self, title, date, start_time, city, address):
        """
        Validates that all required fields are provided.

        Parameters
        ----------
        title : str
            The title of the event.
        date : str
            The date of the event.
        start_time : str
            The start time of the event.
        city : str
            The city where the event is held.
        address : str
            The address where the event is held.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If any of the required fields are missing.
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
        """Save or update the demonstration in the database.

        This method converts the demonstration object to a dictionary and checks if it
        already exists in the database. If it does, the existing entry is updated.
        Otherwise, a new entry is inserted.

        Parameters
        ----------

        Returns
        -------


        """

        # Get the database instance from DatabaseManager
        data = self.to_dict()  # Convert the object to a dictionary

        if data.get("aliases") is None:
            raise ValueError("Aliases are missing.")

        # Check if the demonstration already exists in the database
        if DB["demonstrations"].find_one({"_id": self._id}):
            # Update existing entry
            result = DB["demonstrations"].replace_one({"_id": self._id}, data)
            if result.modified_count:
                print(
                    "Demonstration updated successfully."
                )  # TODO: #191 Use utils.logger instead of print
            else:
                print(
                    "No changes were made to the demonstration."
                )  # TODO: #191 Use utils.logger instead of print
        else:
            # Insert new entry
            DB["demonstrations"].insert_one(data)
            print(
                "Demonstration saved successfully."
            )  # TODO: #191 Use utils.logger instead of print

    @classmethod
    def load_by_id(cls, demo_id: str) -> "Demonstration":
        """
        Load a demonstration by its unique identifier, running number, or slug.
        """
        # Try ObjectId
        try:
            data = DB["demonstrations"].find_one({"_id": ObjectId(demo_id)})
            if data:
                return cls.from_dict(data)
        except Exception:
            pass
        # Try running_number (as int)
        try:
            num = int(demo_id)
            data = DB["demonstrations"].find_one({"running_number": num})
            if data:
                return cls.from_dict(data)
        except Exception:
            pass
        # Try slug
        data = DB["demonstrations"].find_one({"slug": demo_id})
        if data:
            return cls.from_dict(data)
        raise ValueError(f"Demonstration with id/slug/number {demo_id} not found.")
        """
        Load a demonstration by its unique identifier.

        Parameters
        ----------
        demo_id : str
            The unique identifier of the demonstration.

        Returns
        -------
        Demonstration
            An instance of Demonstration loaded from the database.

        Raises
        ------
        ValueError
            If the demonstration with the provided id is not found.
        """
        data = DB["demonstrations"].find_one({"_id": ObjectId(demo_id)})
        if not data:
            raise ValueError(f"Demonstration with id {demo_id} not found.")
        return cls.from_dict(data)

    def _to_iso8601_date(self, date_str: str) -> str:
        """
        Convert a date string to ISO8601 date format (YYYY-MM-DD).

        Parameters
        ----------
        date_str : str
            The date string.

        Returns
        -------
        str
            The ISO8601 formatted date string.

        Raises
        ------
        ValueError
            If date_str is not in the correct format.
        """
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.date().isoformat()
        except ValueError as e:
            try:
                dt = datetime.strptime(date_str, "%d.%m.%Y")
                return dt.date().isoformat()
            except:
                raise ValueError(f"Date is not in ISO8601 format (YYYY-MM-DD): {date_str}") from e

    def _to_iso8601_time(self, time_str: str) -> str:
        """
        Convert a time string to ISO8601 time format (HH:MM:SS).

        If the provided time string is in the format HH:MM, it will be converted to HH:MM:00.
        
        Parameters
        ----------
        time_str : str
            The time string.

        Returns
        -------
        str
            The ISO8601 formatted time string.

        Raises
        ------
        ValueError
            If time_str is not in a recognized time format.
        """
        if is_none(time_str):
            return None
        
        try:
            # If time_str is in HH:MM format, append seconds as "00"
            if time_str.count(":") == 1:
                dt = datetime.strptime(time_str, "%H:%M")
                return dt.time().replace(second=0).isoformat()
            else:
                dt = datetime.strptime(time_str, "%H:%M:%S")
                return dt.time().isoformat()
            
        except ValueError as e:
            raise ValueError(f"Time {time_str} is not in ISO8601 format (HH:MM or HH:MM:SS): {time_str}") from e
        
def is_none(s):
    if s is None:
        return True
    
    if isinstance(s, str) and not s.strip():
        return True
    
    return False
