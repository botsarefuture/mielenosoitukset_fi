from datetime import datetime
from typing import Any, Dict, List, Optional
from bson import ObjectId
from dateutil.relativedelta import relativedelta

from mielenosoitukset_fi.database_manager import DatabaseManager

from .Demonstration import Demonstration
from .RepeatSchedule import RepeatSchedule
from .Organizer import Organizer

from mielenosoitukset_fi.utils.logger import logger

class RecurringDemonstration(Demonstration):
    """
    A demonstration event that repeats over time.

    Extends the base `Demonstration` with recurrence metadata like
    `repeat_schedule` and `created_until`.

    Parameters
    ----------
    *args : Any
        Positional arguments forwarded to `Demonstration`.
    repeat_schedule : RepeatSchedule or dict, optional
        The repeat schedule for this demonstration. Defaults to None.
    created_until : datetime, optional
        The date until which child demonstrations have been generated.
        Defaults to the current datetime.
    **kwargs : Any
        Keyword arguments forwarded to `Demonstration`.

    Attributes
    ----------
    repeat_schedule : RepeatSchedule or None
        Schedule describing how the demonstration repeats.
    created_until : datetime
        Date until which demonstrations have been generated.
    freezed_children : list
        List of child demonstrations that have been frozen.
        These demonstrations will not be automatically modified nor deleted.
    """

    def __init__(
        self,
        *args,
        repeat_schedule: Optional[RepeatSchedule] = None,
        created_until: Optional[datetime] = None,
        freezed_children: Optional[list] = None,
        **kwargs,
    ):
        kwargs["recurs"] = True  # force recurring=True

        # initialize attributes early so super().__init__ can access them safely
        self.repeat_schedule = (
            RepeatSchedule.from_dict(repeat_schedule)
            if isinstance(repeat_schedule, dict)
            else repeat_schedule
        )
        self.created_until = created_until or datetime.now()
        self.freezed_children = freezed_children or []

        super().__init__(*args, **kwargs)

        print(self.freezed_children)


    def calculate_next_dates(self) -> List[datetime]:
        """
        Calculate the next demonstration dates based on the frequency and interval.

        This method calculates the upcoming demonstration dates starting from
        the initial date (`self.date`) and continues until one year from now.
        The calculation is based on the frequency and interval specified
        in `self.repeat_schedule`.

        Returns
        -------
        list of datetime
            List of datetime objects representing the next demonstration dates.
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

        Only the attributes with non-None values will be updated.

        Parameters
        ----------
        **kwargs : Any
            Key-value pairs of attributes to update.

        Returns
        -------
        None
        """
        for attr, value in kwargs.items():
            if value is not None:
                setattr(self, attr, value)

    def to_dict(self, json: bool = False) -> Dict[str, Any]:
        """
        Convert the RecurringDemonstration instance into a dictionary.

        Parameters
        ----------
        json : bool, optional
            If True, ensures JSON serializable output (e.g., ISO formatted datetimes).
            Defaults to False.

        Returns
        -------
        dict
            Dictionary representation of the demonstration.
        """
        data = super().to_dict(json=json)

        data["repeat_schedule"] = (
            self.repeat_schedule.to_dict() if self.repeat_schedule else None
        )
        data["created_until"] = (
            self.created_until.isoformat()
            if getattr(self, "created_until", None)
            else None
        )
        
               
        
        if json:
            _freezed_children = []
            for freezed_children in self.freezed_children:
                _freezed_children.append(str(freezed_children))

            data["freezed_children"] = _freezed_children
            
        else:
            data["freezed_children"] = self.freezed_children

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecurringDemonstration":
        """
        Build an instance from a dictionary.

        Parameters
        ----------
        data : dict
            Dictionary of demonstration data.

        Returns
        -------
        RecurringDemonstration
            Instance of RecurringDemonstration initialized with the data.
        """
        created_until = (
            datetime.fromisoformat(data["created_until"])
            if data.get("created_until")
            else datetime.now()
        )
        
        repeat_schedule = (
            RepeatSchedule.from_dict(data["repeat_schedule"])
            if data.get("repeat_schedule")
            else RepeatSchedule(frequency="none", interval=0)
        )

        data["organizers"] = [
            Organizer.from_dict(org) if isinstance(org, dict) else org
            for org in data.get("organizers", [])
        ]

        def _should_pop_repeat(repeat_schedule, data) -> bool:
            """
            Decide whether the repeat_schedule from the object matches the repeat_schedule in data,
            ignoring 'as_string' and other non-essential fields, treating certain values as equivalent.
            """
            fields_to_compare = [
                "frequency",
                "interval",
                "weekday",
                "monthly_option",
                "day_of_month",
                "nth_weekday",
                "weekday_of_month",
                "end_date",
            ]

            repeat_dict = repeat_schedule.to_dict() if repeat_schedule else {}
            data_dict = data.get("repeat_schedule")
            
            if data_dict is None:
                return True  # Nothing in data → consider it match

            # Pairs of values that should be considered equal
            samsies = [(None, "none")]

            for field in fields_to_compare:
                val_obj = repeat_dict.get(field)
                val_data = data_dict.get(field)

                # Treat samsies pairs as equal
                if (val_obj, val_data) in samsies or (val_data, val_obj) in samsies:
                    continue

                if val_obj != val_data:
                    if val_obj is None:
                        logger.warn(f"Field '{field}' is None in repeat_schedule object: {repeat_dict}")
                    else:
                        logger.warn(f"Field '{field}' mismatch: object={val_obj}, data={val_data}")
                    return False

            return True


        if _should_pop_repeat(repeat_schedule, data):
            print("Popping repeat_schedule from data")
            data.pop("repeat_schedule", None)

        _freezed_children = []
        for freezed_children in data.get("freezed_children", []):
            if isinstance(freezed_children, ObjectId):
                _freezed_children.append(freezed_children)
                
            else:
                try:
                    _freezed_children.append(ObjectId(freezed_children))
                except Exception:
                    logger.warning(f"Skipping invalid ObjectId: {freezed_children}")
                    
        data.pop("freezed_children", None)
        data.pop("created_until", None)

        return cls(
            **data,
            repeat_schedule=repeat_schedule,
            created_until=created_until,
            freezed_children=_freezed_children
        )

    def __repr__(self) -> str:
        """
        Return a string representation of the RecurringDemonstration instance.

        Returns
        -------
        str
            A string containing the title, start time, and end time of the demonstration.
        """
        return (
            f"<RecurringDemonstration(title={self.title}, "
            f"start_time={self.start_time}, end_time={self.end_time})>"
        )

    @classmethod
    def from_id(cls, _id: str) -> "RecurringDemonstration":
        """
        Create an instance of RecurringDemonstration from an ObjectId string.

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

    def save(self) -> None:
        """
        Save the RecurringDemonstration instance to the database.

        If `_id` exists, updates the existing document.
        Otherwise, inserts a new document and sets the `_id`.

        Returns
        -------
        None
        """
        db_man = DatabaseManager.get_instance()
        mongo = db_man.get_db()

        data = self.to_dict()

        if self._id:
            mongo.recu_demos.update_one({"_id": ObjectId(self._id)}, {"$set": data})
        else:
            result = mongo.recu_demos.insert_one(data)
            self._id = result.inserted_id
