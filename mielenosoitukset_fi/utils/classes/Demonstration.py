import copy
import string

from mielenosoitukset_fi.utils.logger import logger
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
  
    """
    A class to represent a demonstration event.

    This class encapsulates the details of a demonstration event, including its title, date, time, location, organizers, media, and other relevant metadata. It provides methods to initialize, validate, manipulate, and save demonstration events.

    Parameters
    ----------
    # --- MANDATORY INFO ---
    title : str
        The title of the event.
    date : str
        The date of the event.
    start_time : str
        The start time of the event.
    end_time : str
        The end time of the event.

    # --- LOCATION INFO ---
    city : str
        The city where the event is held.
    address : str
        The address of the event.
    route : str, optional
        The route of the event if it is a march.
    latitude : str, optional
        Latitude of the event location.
    longitude : str, optional
        Longitude of the event location.

    # --- EXTERNAL LINKS & MEDIA ---
    facebook : str, optional
        Facebook link for the event.
    img : optional
        Image associated with the event.
    preview_image : str, optional
        URL of the preview image for the event.
    cover_picture : str, optional
        URL of the cover picture for the event.

    # --- ORGANIZER & TAG INFO ---
    organizers : list, optional
        List of organizers.
    tags : list, optional
        Tags associated with the event.
    aliases : list, optional
        Aliases for the event.

    # --- RECURRENCE & EVENT TYPE ---
    recurs : bool, optional
        Whether the event is recurring/repeating. Defaults to False.
    event_type : optional
        The type of the event.
    parent : ObjectId, optional
        Parent event ID for recurring events.

    # --- META / SYSTEM INFO ---
    approved : bool, optional
        Whether the event is approved. Defaults to False.
    hide : bool, optional
        Flag to hide the event. Defaults to False.
    in_past : bool, optional
        Whether the event is in the past. Defaults to False.
    merged_into : ObjectId, optional
        ID of the demonstration this one is merged into.
    running_number : int, optional
        Running number for the demonstration.
    slug : str, optional
        URL-friendly slug for the demonstration.
    formatted_date : str, optional
        Pre-formatted date string.
    created_datetime : optional
        Datetime when the event was created.
    _id : ObjectId, optional
        Unique ID for the demonstration.
    description : str, optional
        Description of the event.

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
        # --- MANDATORY INFO ---
        title: str,
        date: str,
        start_time: str,
        end_time: str,

        # --- LOCATION INFO ---
        city: str,
        address: str,
        route: str = None,
        latitude: str = None,
        longitude: str = None,

        # --- EXTERNAL LINKS & MEDIA ---
        facebook: str = None,
        img=None,
        preview_image: str = None,
        cover_picture: str = None,

        # --- ORGANIZER & TAG INFO ---
        organizers: list = None,
        tags: list = None,
        aliases: list = None,

        # --- RECURRENCE & EVENT TYPE ---
        recurs: bool = False,  # replaces repeating + recurring
        event_type=None,
        parent: ObjectId = None,

        # --- META / SYSTEM INFO ---
        approved: bool = False,
        hide: bool = False,
        in_past: bool = False,
        merged_into: ObjectId = None,
        running_number: int = None,
        slug: str = None,
        formatted_date: str = None,
        created_datetime=None,
        last_modified=None,
        _id: ObjectId = None,
        description: str = None,
        _dont_override: bool = False,
        _rejected: bool = False,
        cover_source: str = None,
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

        city : str
            The city where the event is held.
        address : str
            The address of the event.
        route : str, optional
            The route of the event if it is a march.
        latitude : str, optional
            Latitude of the event location.
        longitude : str, optional
            Longitude of the event location.

        facebook : str, optional
            The Facebook link for the event.
        img : optional
            Image associated with the event.
        preview_image : str, optional
            URL of the preview image for the event.
        cover_picture : str, optional
            URL of the cover picture for the event.

        organizers : list, optional
            List of organizers.
        tags : list, optional
            Tags associated with the event.
        aliases : list, optional
            Aliases for the event.

        recurs : bool, optional
            Whether the event is recurring/repeating. Defaults to False.
        event_type : optional
            The type of the event.
        parent : ObjectId, optional
            Parent event ID for recurring events.

        approved : bool, optional
            Whether the event is approved.
        hide : bool, optional
            Flag to hide the event.
        in_past : bool, optional
            Whether the event is in the past.
        merged_into : ObjectId, optional
            ID of the demonstration this one is merged into.
        running_number : int, optional
            Running number for the demonstration.
        slug : str, optional
            URL-friendly slug for the demonstration.
        formatted_date : str, optional
            Pre-formatted date string.
        created_datetime : optional
            Datetime when the event was created.
        _id : ObjectId, optional
            Unique ID for the demonstration.
        description : str, optional
            Description of the event.
        """

        #if issubclass(type(self), Demonstration) and type(self) is not Demonstration:
        self.save_flag = False

        self._dont_override = _dont_override
        
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

        self.formatted_date = self._format_date()

        self.hide = hide

        self.title = title
        self.description = description

        # Removed direct assignment for date, start_time, end_time

        self.city = city
        self.address = address

        self.latitude = latitude
        self.longitude = longitude
        
        if parent:
            try:
                _parent = DB["recu_demos"].find_one({"_id": ObjectId(parent)})
            except Exception as e:
                print(f"Error fetching parent demonstration: {e}")

            if not _parent:
                print(f"Parent demonstration not found")
                self.repeat_schedule = RepeatSchedule()
            else:
                self.parent_object = _parent
                self.repeat_schedule = RepeatSchedule.from_dict(self.parent_object.get("repeat_schedule", None))
                
                

        self.event_type = event_type_convertor(event_type or "STAY_STILL")

        if not valid_event_type(self.event_type):
            raise ValueError(f"Invalid event type: {self.event_type}")

        self.route = route  # If the demonstration is a march, this handles the route
        
        if self.route is not None and not isinstance(self.route, list):
            try:
                self.route = [x.strip() for x in self.route.split(",") if x.strip()]
            except Exception:
                pass
        


        # EXTERNAL LINKS
        self.facebook = facebook

        self.approved = approved
        
        self._id = _id or ObjectId()  # Unique ID for the demonstration
        self.running_number = running_number
        self.slug = slug
        
        self.tags = tags or []  # Tags for the demonstration

        self.created_datetime = created_datetime or None
        # last_modified stores the last time this object was changed and saved
        # If provided, use it; otherwise set to current UTC time
        self.last_modified = last_modified or datetime.utcnow()

        # RECURRING DEMO STUFF
        self.parent: ObjectId = parent or None
        
        self.recurs = recurs or False
        
        if self.parent:
            self.recurs = True
            self.save_flag = True
            
        if _rejected == True:
            self.accepted = False
            self.hide = True
            self.save_flag = True

        

        # Initialize organizers
        self.organizers = [
            Organizer.from_dict(org) if isinstance(org, dict) else org
            for org in (organizers or [])
        ]

        self.in_past = in_past  # Whether or not in past

        self.aliases = aliases or []
        self.alias_fix()

        # IMAGES
        self.preview_image = preview_image
        self.img = img
        self.cover_picture = cover_picture
        self.cover_source = cover_source
        
        if not self.cover_picture:

            if self.img:
                # user-chosen image takes priority
                self.cover_picture = self.img
                self.cover_source = "user"
                
            elif self.preview_image:
                # fallback to auto-generated preview
                self.cover_picture = self.preview_image
                self.cover_source = "automatic"

            else:
                self.cover_picture = None
                self.cover_source = None
                
        else:
            self.cover_picture = cover_picture
            self.cover_source = cover_source
            

        def build_url(self):
            return '/static/demo_preview/' + str(self._id) + '.png'
    
            
        if self.preview_image is not None and self.preview_image.startswith("/static/demo_preview/"):
            # add https://mielenosoitukset.fi/ to the beginning of the URL
            self.preview_image = "https://mielenosoitukset.fi" + self.preview_image
            self.save_flag = True # Save the demonstration to update the preview image
        
        self.merged_into = merged_into  # Assign new parameter

        if self.save_flag and not self._dont_override:  # Save the demonstration if the save_flag is set
            self.save()  # Save the demonstration

        self.validate_fields(
            title, date, start_time, city, address
        )  # Validate required fields


    def _format_date(self):
        if self.date:
            try:
                return datetime.strptime(self.date, '%Y-%m-%d').strftime('%d.%m.%Y')
            except ValueError:
                return self.date  # fallback if the format is wrong
        return None


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
            
        # TODO: Let's check the version history and keep the never info if it's newer than the recurring demo's info
        # For now we just keep overriding title, description, tags, and organizers which is not ideal
        # Maybe we should implement a function to compare and merge these fields intelligently
        

        self.title = recurring_demo.title
        self.description = recurring_demo.description
        self.tags = recurring_demo.tags
        self.organizers = recurring_demo.organizers

        self.save()

    def _merge_fields(self, recurring_demo: "RecurringDemonstration"):
        """Merge fields from a recurring demonstration into the current demonstration.

        This method intelligently merges fields from a recurring demonstration into the
        current demonstration, keeping the most recent information.

        Parameters
        ----------
        recurring_demo : RecurringDemonstration
            The recurring demonstration instance.

        Returns
        -------
        None
        """
        # TODO: Implement intelligent merging of fields
        pass

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
        # Include last_modified in the dictionary. If JSON output is requested,
        # convert datetimes to ISO strings.
        try:
            if hasattr(self, "last_modified") and self.last_modified is not None:
                if json:
                    data["last_modified"] = (
                        self.last_modified.isoformat()
                    )
                else:
                    data["last_modified"] = self.last_modified
            else:
                data["last_modified"] = None
        except Exception as e:
            data["last_modified"] = None
            logger.error(f"Error converting last_modified to dict: {e}")
        data.pop("save_flag", None)  # Remove save_flag from the dictionary representation
        data.pop("_dont_override", None)
        try:
            data["repeat_schedule"] = self.repeat_schedule.to_dict() if hasattr(self, "repeat_schedule") and self.repeat_schedule else None
        except Exception as e:
            data["repeat_schedule"] = None
            logger.error(f"Error converting repeat_schedule to dict: {e}")
            
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

        # Update last_modified to now and prepare data for saving
        self.last_modified = datetime.utcnow()

        # Get the database instance from DatabaseManager
        data = self.to_dict()  # Convert the object to a dictionary

        _data = copy.deepcopy(data)
        
        data = _data

        if data.get("aliases") is None:
            raise ValueError("Aliases are missing.")
        
        data.pop("repeat_schedule", None)  # Remove repeat_schedule if present
        data.pop("parent_object", None)  # Remove parent_object if present
        
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

        Parameters
        ----------
        demo_id : str
            The unique identifier (ObjectId as str), running number, or slug of the demonstration.

        Returns
        -------
        Demonstration
            An instance of Demonstration loaded from the database.

        Raises
        ------
        ValueError
            If the demonstration with the provided id/number/slug is not found.
        """
        # Try ObjectId lookup68b9748683ca07b64b6cd87e
        try:
            obj_id = ObjectId(demo_id)
            data = DB["demonstrations"].find_one({"_id": obj_id})
            if data:
                logger.info("Found")
                return cls.from_dict(data)

        except Exception as e:
            logger.debug(f"ObjectId lookup failed for '{demo_id}': {e}")

        # Try running_number lookup
        try:
            num = int(demo_id)
            data = DB["demonstrations"].find_one({"running_number": num})
            if data:
                return cls.from_dict(data)
        except ValueError:
            logger.debug(f"Running number lookup failed for '{demo_id}'")
        except Exception as e:
            pass

        # Try slug lookup
        data = DB["demonstrations"].find_one({"slug": demo_id})
        if data:
            return cls.from_dict(data)

        # Nothing found
        raise ValueError(f"Demonstration with id/slug/number '{demo_id}' not found.")

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
            # Basic Info
            title=get("title"),
            description=get("description"),
            date=get("date"),
            start_time=get("start_time"),
            end_time=get("end_time"),

            # Location
            city=get("city"),
            address=get("address"),
            route=get("route"),
            latitude=get("latitude"),
            longitude=get("longitude"),

            # External Links & Media
            facebook=get("facebook"),
            img=get("img"),
            preview_image=get("preview_image"),
            cover_picture=get("cover_picture"),
            cover_source=get("cover_source"),

            # Organizers & Tags
            organizers=get("organizers"),
            tags=get("tags") or [],
            aliases=get("aliases") or [],

            # Recurrence & Event Type
            recurs=get("recurs", False),
            event_type=get("event_type"),
            parent=get("parent"),


            # Meta & System Fields
            approved=get("approved", False),
            _rejected=get("rejected", False),
            
            hide=get("hide", False),
            in_past=get("in_past", False),
            
            created_datetime=get("created_datetime"),
            last_modified=get("last_modified"),
            merged_into=get("merged_into"),
            
            _id=get("_id"),            
            running_number=get("running_number"),
            slug=get("slug"),
        )


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
