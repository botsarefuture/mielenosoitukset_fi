from datetime import datetime
from typing import Any, Dict, Optional


class RepeatSchedule:
    """Class to handle repeat schedules for recurring demonstrations."""

    def __init__(
        self,
        frequency: str,
        interval: int,
        weekday: Optional[str] = None,
        monthly_option: Optional[str] = None,
        day_of_month: Optional[int] = None,
        nth_weekday: Optional[str] = None,
        weekday_of_month: Optional[str] = None,
        end_date: Optional[str] = None,
    ):
        self.frequency = frequency
        self.interval = interval
        self.weekday = weekday
        self.monthly_option = monthly_option
        self.day_of_month = day_of_month
        self.nth_weekday = nth_weekday
        self.weekday_of_month = weekday_of_month
        self.end_date = end_date

    def as_string(self) -> str:
        """Return a string representation of the repeat schedule."""
        frequency_map = {
            "daily": "daily",
            "weekly": "weekly",
            "monthly": "monthly",
            "yearly": "yearly",
        }

        weekday_str = (
            f" on {self.weekday}"
            if self.frequency == "weekly" and self.weekday
            else ""
        )

        monthly_str = ""
        if self.frequency == "monthly":
            if self.monthly_option == "day_of_month" and self.day_of_month:
                monthly_str = f" on day {self.day_of_month} of each month"
            elif self.monthly_option == "nth_weekday" and self.nth_weekday and self.weekday_of_month:
                monthly_str = f" on the {self.nth_weekday} {self.weekday_of_month} of each month"

        return (
            f"every {self.interval} {frequency_map.get(self.frequency, 'unknown')}s{weekday_str}{monthly_str}"
            if self.interval > 1
            else frequency_map.get(self.frequency, "unknown") + weekday_str + monthly_str
        )

    def __str__(self) -> str:
        return self.as_string()

    def to_dict(self) -> Dict[str, Any]:
        """Convert the repeat schedule to a dictionary."""
        return {
            "frequency": self.frequency,
            "interval": self.interval,
            "weekday": self.weekday,
            "monthly_option": self.monthly_option,
            "day_of_month": self.day_of_month,
            "nth_weekday": self.nth_weekday,
            "weekday_of_month": self.weekday_of_month,
            "end_date": self.end_date,
            "as_string": str(self),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RepeatSchedule":
        """Create a RepeatSchedule instance from a dictionary.

        Parameters
        ----------
        data : Dict[str, Any]
            The dictionary containing repeat schedule data.

        Returns
        -------
        RepeatSchedule
            The created RepeatSchedule instance.
        """
        return cls(
            frequency=data["frequency"],
            interval=data["interval"],
            weekday=data.get("weekday"),
            monthly_option=data.get("monthly_option"),
            day_of_month=data.get("day_of_month"),
            nth_weekday=data.get("nth_weekday"),
            weekday_of_month=data.get("weekday_of_month"),
            end_date=data.get("end_date"),
        )
