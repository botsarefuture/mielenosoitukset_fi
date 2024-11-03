from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import List, Optional, Dict, Any


class RepeatSchedule:
    def __init__(self, frequency: str, interval: int, weekday: Optional[datetime] = None):
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

        weekday_str = f" on {self.weekday.strftime('%A')}" if self.frequency == "weekly" and self.weekday else ""
        return (
            f"every {self.interval} {frequency_map.get(self.frequency, 'unknown')}s{weekday_str}"
            if self.interval > 1
            else frequency_map.get(self.frequency, 'unknown') + weekday_str
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


class RecurringDemonstration:
    def __init__(
        self,
        title: str,
        start_time: datetime,
        end_time: datetime,
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
        next_dates = []
        demo_date = self.start_time
        end_date = datetime.now() + relativedelta(years=1)

        while demo_date <= end_date:
            if demo_date > (self.created_until or datetime.now()):
                next_dates.append(demo_date)

            demo_date = {
                "daily": demo_date + relativedelta(days=self.repeat_schedule.interval),
                "weekly": demo_date + relativedelta(
                    weeks=self.repeat_schedule.interval, days=((self.repeat_schedule.weekday.weekday() - demo_date.weekday() + 7) % 7)
                ) if self.repeat_schedule.weekday else demo_date + relativedelta(weeks=self.repeat_schedule.interval),
                "monthly": demo_date + relativedelta(months=self.repeat_schedule.interval),
                "yearly": demo_date + relativedelta(years=self.repeat_schedule.interval)
            }.get(self.repeat_schedule.frequency, demo_date)

        return next_dates

    def update_demo(
        self,
        title: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        facebook: Optional[str] = None,
        city: Optional[str] = None,
        address: Optional[str] = None,
        demo_type: Optional[str] = None,
        route: Optional[str] = None,
        organizers: Optional[List[str]] = None,
        linked_organizations: Optional[List[str]] = None,
    ) -> None:
        """Update demonstration details."""
        for attr, value in locals().items():
            if value is not None and attr != "self":
                setattr(self, attr, value)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the object to a dictionary for easy storage in a database."""
        return {
            "title": self.title,
            "start_time": self.start_time.strftime("%d.%m.%Y %H:%M"),
            "end_time": self.end_time.strftime("%d.%m.%Y %H:%M"),
            "facebook": self.facebook,
            "city": self.city,
            "address": self.address,
            "type": self.type,
            "route": self.route,
            "organizers": self.organizers,
            "linked_organizations": self.linked_organizations,
            "repeat_schedule": self.repeat_schedule.to_dict() if self.repeat_schedule else None,
            "created_until": self.created_until.strftime("%d.%m.%Y") if self.created_until else datetime.now().strftime("%d.%m.%Y"),
            "created_datetime": self.created_datetime.strftime("%d.%m.%Y %H:%M"),
            "_id": str(self._id) if self._id else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecurringDemonstration":
        """Create an instance from a dictionary."""
        try:
            start_time = datetime.strptime(data["start_time"], "%d.%m.%Y %H:%M")
            end_time = datetime.strptime(data["end_time"], "%d.%m.%Y %H:%M")
            created_until = datetime.strptime(data["created_until"], "%d.%m.%Y") if data.get("created_until") else datetime.now()
        except ValueError as e:
            raise ValueError("Date format is incorrect") from e

        return cls(
            title=data["title"],
            start_time=start_time,
            end_time=end_time,
            facebook=data["facebook"],
            city=data["city"],
            address=data["address"],
            demo_type=data["type"],
            route=data["route"],
            organizers=data.get("organizers", []),
            linked_organizations=data.get("linked_organizations", []),
            repeat_schedule=RepeatSchedule.from_dict(data["repeat_schedule"]) if data.get("repeat_schedule") else None,
            created_until=created_until,
            _id=data.get("_id"),
        )

    def __repr__(self) -> str:
        return f"<RecurringDemonstration(title={self.title}, start_time={self.start_time}, end_time={self.end_time})>"
