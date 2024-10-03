from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import List, Optional, Dict, Any


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

        # Check for weekday if frequency is weekly
        weekday_str = ""
        if self.frequency == "weekly" and self.weekday is not None:
            weekday_name = self.weekday.strftime("%A")
            weekday_str = f" on {weekday_name}"

        if self.frequency in frequency_map:
            return (
                f"every {self.interval} {frequency_map[self.frequency]}{'s' if self.interval > 1 else ''}{weekday_str}"
                if self.interval > 1
                else frequency_map[self.frequency] + weekday_str
            )

        return "unknown frequency"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frequency": self.frequency,
            "interval": self.interval,
            "weekday": self.weekday if self.weekday else None,
            "as_string": self.__str__(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RepeatSchedule":
        return cls(
            frequency=data["frequency"],
            interval=data["interval"],
            weekday=data.get("weekday"),
        )


class RecurringDemonstration:
    def __init__(
        self,
        title: str,
        start_time: datetime,
        end_time: datetime,
        topic: str,
        facebook: str,
        city: str,
        address: str,
        demo_type: str,
        route: str,
        organizers: Optional[List[str]] = None,
        linked_organizations: Optional[List[str]] = None,
        repeat_schedule: Optional[RepeatSchedule] = None,
        created_until: Optional[datetime] = None,
        _id: Optional[str] = None,
    ):
        self.title = title
        self.start_time = start_time
        self.end_time = end_time
        self.topic = topic
        self.facebook = facebook
        self.city = city
        self.address = address
        self.type = demo_type
        self.route = route
        self.organizers = organizers or []
        self.linked_organizations = linked_organizations or []
        self.repeat_schedule = repeat_schedule
        self.created_until = created_until or datetime.now()
        self.created_datetime = datetime.now()
        self._id = _id

    def calculate_next_dates(self) -> List[datetime]:
        """Calculate the next demonstration dates based on the frequency and interval."""
        current_date = datetime.now()
        next_dates = []
        end_date = current_date + relativedelta(years=1)

        demo_date = self.start_time
        while demo_date <= end_date:
            if demo_date > self.created_until:
                next_dates.append(demo_date)

            if self.repeat_schedule.frequency == "daily":
                demo_date += relativedelta(days=self.repeat_schedule.interval)
            elif self.repeat_schedule.frequency == "weekly":
                if self.repeat_schedule.weekday:
                    days_ahead = (
                        self.repeat_schedule.weekday.weekday() - demo_date.weekday() + 7
                    ) % 7
                    demo_date += relativedelta(
                        weeks=self.repeat_schedule.interval, days=days_ahead
                    )
                else:
                    demo_date += relativedelta(weeks=self.repeat_schedule.interval)
            elif self.repeat_schedule.frequency == "monthly":
                demo_date += relativedelta(months=self.repeat_schedule.interval)
            elif self.repeat_schedule.frequency == "yearly":
                demo_date += relativedelta(years=self.repeat_schedule.interval)

        return next_dates

    def update_demo(
        self,
        title: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        topic: Optional[str] = None,
        facebook: Optional[str] = None,
        city: Optional[str] = None,
        address: Optional[str] = None,
        demo_type: Optional[str] = None,
        route: Optional[str] = None,
        organizers: Optional[List[str]] = None,
        linked_organizations: Optional[List[str]] = None,
    ) -> None:
        """Update demonstration details."""
        if title:
            self.title = title
        if start_time:
            self.start_time = start_time
        if end_time:
            self.end_time = end_time
        if topic:
            self.topic = topic
        if facebook:
            self.facebook = facebook
        if city:
            self.city = city
        if address:
            self.address = address
        if demo_type:
            self.type = demo_type
        if route:
            self.route = route
        if organizers is not None:
            self.organizers = organizers or []
        if linked_organizations is not None:
            self.linked_organizations = linked_organizations or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert the object to a dictionary for easy storage in a database."""
        return {
            "title": self.title,
            "start_time": self.start_time.strftime("%d.%m.%Y %H:%M"),
            "end_time": self.end_time.strftime("%d.%m.%Y %H:%M"),
            "topic": self.topic,
            "facebook": self.facebook,
            "city": self.city,
            "address": self.address,
            "type": self.type,
            "route": self.route,
            "organizers": self.organizers,
            "linked_organizations": self.linked_organizations,
            "repeat_schedule": (
                self.repeat_schedule.to_dict() if self.repeat_schedule else None
            ),
            "created_until": (
                self.created_until.strftime("%d.%m.%Y")
                if self.created_until
                else datetime.now().strftime("%d.%m.%Y")
            ),
            "created_datetime": self.created_datetime.strftime("%d.%m.%Y %H:%M"),
            "_id": str(self._id if self._id else "None"),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecurringDemonstration":
        """Create an instance from a dictionary."""
        try:
            start_time = datetime.strptime(data["start_time"], "%d.%m.%Y %H:%M")
            end_time = datetime.strptime(data["end_time"], "%d.%m.%Y %H:%M")
            created_until = (
                datetime.strptime(data["created_until"], "%d.%m.%Y")
                if data.get("created_until")
                else datetime.now()
            )
        except ValueError as e:
            raise ValueError("Date format is incorrect") from e

        return cls(
            title=data["title"],
            start_time=start_time,
            end_time=end_time,
            topic=data["topic"],
            facebook=data["facebook"],
            city=data["city"],
            address=data["address"],
            demo_type=data["type"],
            route=data["route"],
            organizers=data.get("organizers", []),
            linked_organizations=data.get("linked_organizations", []),
            repeat_schedule=RepeatSchedule.from_dict(data.get("repeat_schedule", {})),
            created_until=created_until,
            _id=data.get("_id"),
        )

    def __repr__(self) -> str:
        return f"<RecurringDemonstration(title={self.title}, start_time={self.start_time}, end_time={self.end_time})>"
