from datetime import datetime
from typing import Any, Dict, List, Optional
from bson import ObjectId
from dateutil.relativedelta import relativedelta

from mielenosoitukset_fi.database_manager import DatabaseManager

from .Demonstration import Demonstration
from .RepeatSchedule import RepeatSchedule
from .Organizer import Organizer


class RecurringDemonstration(Demonstration):
    """ """

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
        cover_picture: str = None,  # Added field
    ):
        """
        Initialize a new recurring demonstration event.

        Parameters
        ----------
        title : str
            The title of the demonstration.
        date : str
            The date of the demonstration in YYYY-MM-DD format.
        start_time : str
            The start time of the demonstration in HH:MM format.
        end_time : str
            The end time of the demonstration in HH:MM format.
        facebook : str
            The Facebook event URL.
        city : str
            The city where the demonstration will take place.
        address : str
            The address of the demonstration location.
        route : str
            The route of the demonstration.
        organizers : list, optional
            A list of organizers for the demonstration. Defaults to None.
        approved : bool, optional
            Whether the demonstration is approved. Defaults to False.
        linked_organizations : dict, optional
            A dictionary of linked organizations. Defaults to None.
        img : optional
            An image for the demonstration. Defaults to None.
        _id : optional
            The ID of the demonstration. Defaults to None.
        description : str, optional
            A description of the demonstration. Defaults to None.
        tags : list, optional
            A list of tags for the demonstration. Defaults to None.
        parent : ObjectId, optional
            The parent ID for the demonstration. Defaults to None.
        created_datetime : optional
            The creation date and time of the demonstration. Defaults to None.
        recurring : bool, optional
            Whether the demonstration is recurring. Defaults to False.
        topic : str, optional
            The topic of the demonstration. Defaults to None.
        type : str, optional
            The type of the demonstration. Defaults to None.
        repeat_schedule : RepeatSchedule, optional
            The repeat schedule for the demonstration. Defaults to None.
        repeating : bool, optional
            Whether the demonstration is repeating. Defaults to False.
        latitude : str, optional
            The latitude of the demonstration location. Defaults to None.
        longitude : str, optional
            The longitude of the demonstration location. Defaults to None.
        event_type : optional
            The event type. Defaults to None.
        save_flag : bool, optional
            Whether to save the demonstration. Defaults to False.
        hide : bool, optional
            Whether to hide the demonstration. Defaults to False.
        created_until : Optional[datetime], optional
            The date until which the demonstration is created. Defaults to None.
        cover_picture : str, optional
            URL of the cover picture for the event. Defaults to None.
        """

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
            cover_picture=cover_picture,  # Pass to parent
        )

        # Set created_until to now if not provided
        self.created_until = created_until or datetime.now()
        self.repeat_schedule = repeat_schedule

    def calculate_next_dates(self) -> List[datetime]:
        """Calculate the next demonstration dates based on the frequency and interval.

        This method calculates the upcoming demonstration dates starting from the initial
        date (`self.date`) and continues until one year from the current date. The calculation
        is based on the frequency and interval specified in `self.repeat_schedule`.

        Parameters
        ----------

        Returns
        -------


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
        """Update demonstration details using keyword arguments.

        This method allows updating the attributes of the demonstration instance
        by passing keyword arguments. Only the attributes with non-None values
        will be updated.

        Parameters
        ----------
        **kwargs :


        Returns
        -------


        """

        for attr, value in kwargs.items():
            if value is not None:
                setattr(self, attr, value)

    def to_dict(self, json=False) -> Dict[str, Any]:
        """Convert the object to a dictionary for easy storage in a database.

        Parameters
        ----------
        json : bool
            If True, the dictionary will be JSON serializable. (Default value = False)

        Returns
        -------


        """

        data = super().to_dict(json=json)  # Call the parent to_dict

        if isinstance(self.repeat_schedule, dict):
            self.repeat_schedule = RepeatSchedule.from_dict(self.repeat_schedule)

        data["repeat_schedule"] = (
            self.repeat_schedule.to_dict() if self.repeat_schedule else None
        )

        if self.created_until:
            if isinstance(self.created_until, datetime):
                data["created_until"] = self.created_until.isoformat()
            else:
                data["created_until"] = datetime.fromisoformat(data["created_until"]).isoformat() if self.created_until is not None else None
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecurringDemonstration":
        """Create an instance of RecurringDemonstration from a dictionary.

        Parameters
        ----------
        data : Dict[str
            A dictionary containing the data to create the instance.
        data :
            Dict[str:
        Any :
            returns: An instance of the RecurringDemonstration class.
        data : Dict[str :

        Any] :

        data : Dict[str :

        data : Dict[str :

        data: Dict[str :


        Returns
        -------


        """

        created_until = (
            datetime.fromisoformat(data["created_until"]) if data.get("created_until") else datetime.now()
        )

        return cls(
            title=data["title"],
            date=data["date"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            facebook=data["facebook"],
            city=data["city"],
            address=data["address"],
            route=data["route"],
            organizers=[
                Organizer.from_dict(org) if isinstance(org, dict) else org
                for org in data.get("organizers", [])
            ],
            approved=data.get("approved", False),
            linked_organizations=data.get("linked_organizations", {}),
            img=data.get("img"),
            _id=data.get("_id"),
            description=data.get("description"),
            tags=data.get("tags", []),
            parent=ObjectId(data["parent"]) if data.get("parent") else None,
            created_datetime=data.get("created_datetime"),
            recurring=True,
            topic=data.get("topic"),
            type=data.get("type"),
            repeat_schedule=(
                RepeatSchedule.from_dict(data["repeat_schedule"])
                if data.get("repeat_schedule")
                else None
            ),
            repeating=data.get("repeating", False),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            event_type=data.get("event_type"),
            save_flag=data.get("save_flag", False),
            hide=data.get("hide", False),
            created_until=created_until,
        )

    def __repr__(self) -> str:
        """
        Return a string representation of the RecurringDemonstration instance.

        Returns:
            str: A string containing the title, start time, and end time of the demonstration.
        """
        return f"<RecurringDemonstration(title={self.title}, start_time={self.start_time}, end_time={self.end_time})>"

    @classmethod
    def from_id(cls, _id: str) -> "RecurringDemonstration":
        """Create an instance of RecurringDemonstration from an ObjectId string.

        Parameters
        ----------
        _id : str
            The ObjectId string to create the instance from.

        Returns
        -------
        RecurringDemonstration
            An instance of the RecurringDemonstration class.
        """
        db_man = DatabaseManager.get_instance()
        mongo = db_man.get_db()
        
        data = mongo.recu_demos.find_one({"_id": ObjectId(_id)})
        return cls.from_dict(data)
        return cls(_id=_id)