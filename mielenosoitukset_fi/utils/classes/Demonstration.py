from .BaseModel import BaseModel
from .Organizer import Organizer
from mielenosoitukset_fi.utils.database import get_database_manager
from mielenosoitukset_fi.utils.validators import event_type_convertor, valid_event_type, return_exists
from .RepeatSchedule import RepeatSchedule
from bson import ObjectId


DB = get_database_manager()


class Demonstration(BaseModel):
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

        Notes
        -----
        .. deprecated:: 1.6.0
            `topic` will be removed in a future version.
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

        self.event_type = event_type_convertor(type or event_type)

        if not valid_event_type(self.event_type):
            raise ValueError(f"Invalid event type: {self.event_type}")

        self.route = route  # If the demonstration is a march, this handles the route

        self.img = img

        # EXTERNAL LINKS
        self.facebook = facebook

        self.approved = approved
        self.linked_organizations = linked_organizations or {}  # What is this used for?
        # TODO: #232 Remove linked_organizations if not used

        self._id = _id or ObjectId()  # Unique ID for the demonstration
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

    def update_self_from_recurring(self, recurring_demo: 'RecurringDemonstration'):
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
        if not isinstance(recurring_demo, Demonstration): # RecurringDemonstration is a subclass of Demonstration, so it will return True
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