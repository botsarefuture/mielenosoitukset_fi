from datetime import datetime
from typing import Any, Dict, Optional

from mielenosoitukset_fi.utils import logger


class RepeatSchedule:
    """
    Represents a repeat schedule for recurring demonstrations.

    This class encapsulates scheduling metadata such as frequency,
    interval, and optional conditions like specific weekdays or monthly options.

    Parameters
    ----------
    frequency : str
        Frequency of the repetition. Supported values are:
        ``"none"``, ``"daily"``, ``"weekly"``, ``"monthly"``, ``"yearly"``.
    interval : int
        The interval between occurrences, depending on the frequency.
        Must be greater than or equal to 1.
    weekday : str, optional
        Day of the week when frequency is ``"weekly"``.
        Supported values are: ``"monday"``, ``"tuesday"``, ``"wednesday"``,
        ``"thursday"``, ``"friday"``, ``"saturday"``, ``"sunday"``.
    monthly_option : str, optional
        Option for monthly repetition. Supported values are:
        ``"day_of_month"`` or ``"nth_weekday"``.
    day_of_month : int, optional
        Specific day of the month (1–31) for monthly repetition when
        ``monthly_option="day_of_month"``.
    nth_weekday : str, optional
        Descriptor for nth weekday repetition, e.g., ``"first"``, ``"second"``,
        ``"third"``, ``"fourth"``, ``"last"``. Used with ``monthly_option="nth_weekday"``.
    weekday_of_month : str, optional
        Weekday name when ``monthly_option="nth_weekday"`` is chosen.
        Same supported values as ``weekday``.
    end_date : str, optional
        ISO 8601 formatted string representing when the schedule ends.
        If ``None``, the schedule continues indefinitely.

    Raises
    ------
    ValueError
        If provided parameters are invalid (e.g., unsupported frequency,
        invalid interval, or invalid weekday).
    """

    VALID_FREQUENCIES = {"none", "daily", "weekly", "monthly", "yearly"}
    VALID_WEEKDAYS = {
        "monday", "tuesday", "wednesday",
        "thursday", "friday", "saturday", "sunday"
    }
    VALID_MONTHLY_OPTIONS = {"day_of_month", "nth_weekday"}
    VALID_NTH_WEEKDAYS = {"first", "second", "third", "fourth", "last"}

    def __init__(
        self,
        frequency: str = "none",
        interval: int = 0,
        weekday: Optional[str] = None,
        monthly_option: Optional[str] = None,
        day_of_month: Optional[int] = None,
        nth_weekday: Optional[str] = None,
        weekday_of_month: Optional[str] = None,
        end_date: Optional[str] = None,
    ):
        """
        Initialize a RepeatSchedule with validation.

        Parameters
        ----------
        frequency : str, default="none"
            How often the event repeats. Must be one of {"none","daily","weekly","monthly","yearly"}.
        interval : int, default=0
            The interval at which the repetition occurs. Must be 0 if frequency="none",
            otherwise must be >=1.
        weekday : str, optional
            Weekday name (for weekly schedules).
        monthly_option : str, optional
            Option for monthly scheduling. Must be one of {"day_of_month","nth_weekday"}.
        day_of_month : int, optional
            Day of month (1–31), used when monthly_option="day_of_month".
        nth_weekday : str, optional
            Nth occurrence ("first","second","third","fourth","last"), used when monthly_option="nth_weekday".
        weekday_of_month : str, optional
            Weekday of month, used together with nth_weekday.
        end_date : str, optional
            ISO 8601 date string (YYYY-MM-DD) when recurrence ends.
        """
        
        # Frequency validation
        if frequency not in self.VALID_FREQUENCIES:
            raise ValueError(f"Invalid frequency '{frequency}'. Must be one of {self.VALID_FREQUENCIES}.")

        # Interval validation
        if frequency == "none":
            if interval != 0:
                raise ValueError("Interval must be 0 when frequency is 'none'.")
        else:
            if interval < 1:
                raise ValueError("Interval must be >= 1 when frequency is not 'none'.")

        # Weekday validation
        if weekday and weekday.lower() not in self.VALID_WEEKDAYS:
            raise ValueError(f"Invalid weekday '{weekday}'. Must be one of {self.VALID_WEEKDAYS}.")

        # Monthly options validation
        if monthly_option:
            if monthly_option not in self.VALID_MONTHLY_OPTIONS:
                raise ValueError(
                    f"Invalid monthly_option '{monthly_option}'. Must be one of {self.VALID_MONTHLY_OPTIONS}."
                )

            if monthly_option == "day_of_month":
                if not day_of_month or not (1 <= day_of_month <= 31):
                    raise ValueError("day_of_month must be between 1 and 31 when monthly_option='day_of_month'.")

            elif monthly_option == "nth_weekday":
                if not nth_weekday or nth_weekday.lower() not in self.VALID_NTH_WEEKDAYS:
                    raise ValueError(
                        f"Invalid nth_weekday '{nth_weekday}'. Must be one of {self.VALID_NTH_WEEKDAYS}."
                    )
                if not weekday_of_month or weekday_of_month.lower() not in self.VALID_WEEKDAYS:
                    raise ValueError(
                        f"Invalid weekday_of_month '{weekday_of_month}'. Must be one of {self.VALID_WEEKDAYS}."
                    )

        # End date validation
        if end_date:
            try:
                datetime.fromisoformat(end_date)
            except ValueError:
                raise ValueError(f"Invalid end_date format '{end_date}'. Must be ISO 8601 string (YYYY-MM-DD).")

        # Assign (normalize to lowercase when relevant)
        self.frequency = frequency
        self.interval = interval
        self.weekday = weekday.lower() if weekday else None
        self.monthly_option = monthly_option
        self.day_of_month = day_of_month
        self.nth_weekday = nth_weekday.lower() if nth_weekday else None
        self.weekday_of_month = weekday_of_month.lower() if weekday_of_month else None
        self.end_date = end_date

    def as_string(self) -> str:
        """
        Return a human-readable string representation of the repeat schedule.

        Returns
        -------
        str
            Human-readable schedule description.
        """
        frequency_map = {
            "daily": "day",
            "weekly": "week",
            "monthly": "month",
            "yearly": "year",
            "none": "no repeat"
        }

        weekday_str = (
            f" on {self.weekday.capitalize()}" if self.frequency == "weekly" and self.weekday else ""
        )

        monthly_str = ""
        if self.frequency == "monthly":
            if self.monthly_option == "day_of_month" and self.day_of_month:
                monthly_str = f" on day {self.day_of_month}"
            elif self.monthly_option == "nth_weekday" and self.nth_weekday and self.weekday_of_month:
                monthly_str = f" on the {self.nth_weekday} {self.weekday_of_month.capitalize()}"

        base = f"every {self.interval} {frequency_map.get(self.frequency, 'unknown')}{'s' if self.interval > 1 else ''}"
        return base + weekday_str + monthly_str

    def __str__(self) -> str:
        return self.as_string()

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the repeat schedule to a dictionary.

        Returns
        -------
        dict
            Dictionary representation of the repeat schedule.
        """
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
        """
        Create a RepeatSchedule instance from a dictionary.

        Parameters
        ----------
        data : dict
            Dictionary of repeat schedule data.

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
