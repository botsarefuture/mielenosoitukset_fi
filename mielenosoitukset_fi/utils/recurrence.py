"""Pure recurring-date calculation shared by workers and admin previews."""

from datetime import date, datetime, timedelta
from typing import Optional, Union

from dateutil.relativedelta import relativedelta, weekday

from mielenosoitukset_fi.utils.classes.RepeatSchedule import RepeatSchedule


WEEKDAY_MAP = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def next_weekday(value: date, target_weekday: str, interval: int = 1) -> date:
    """Advance to the next requested weekday at the configured week interval."""
    target = WEEKDAY_MAP[target_weekday.lower()]
    days_until = (target - value.weekday()) % 7
    if days_until == 0:
        days_until = 7 * interval
    else:
        days_until += 7 * (interval - 1)
    return value + timedelta(days=days_until)


def calculate_recurrence_dates(
    start_date: Union[datetime, date],
    schedule: RepeatSchedule,
    created_until: Optional[Union[datetime, date]] = None,
    *,
    max_occurrences: int = 1000,
    today: Optional[date] = None,
) -> list[date]:
    """Return occurrence dates using the recurring-worker scheduling contract."""
    frequency = schedule.frequency
    interval = schedule.interval or 1
    current_date = today or datetime.now().date()
    occurrences = []

    end_date = schedule.end_date
    if not end_date:
        end_date = current_date + relativedelta(years=1)
    elif isinstance(end_date, str):
        try:
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            end_date = current_date + relativedelta(years=1)

    if isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(created_until, datetime):
        created_until = created_until.date()
    if created_until and created_until > start_date:
        start_date = created_until

    occurrence_date = start_date
    iterations = 0
    while (
        occurrence_date <= end_date
        and len(occurrences) < max_occurrences
        and iterations < 10000
    ):
        if occurrence_date >= current_date and (
            not created_until or occurrence_date > created_until
        ):
            occurrences.append(occurrence_date)

        try:
            if frequency == "daily":
                occurrence_date += timedelta(days=interval)
            elif frequency == "weekly":
                if schedule.weekday:
                    occurrence_date = next_weekday(
                        occurrence_date,
                        schedule.weekday,
                        interval=interval,
                    )
                else:
                    occurrence_date += timedelta(weeks=interval)
            elif frequency == "monthly":
                if schedule.monthly_option == "day_of_month":
                    occurrence_date += relativedelta(
                        months=interval,
                        day=schedule.day_of_month,
                    )
                elif schedule.monthly_option == "nth_weekday":
                    occurrence_date = (
                        occurrence_date + relativedelta(months=interval)
                    ).replace(day=1)
                    weekday_number = WEEKDAY_MAP[schedule.weekday_of_month]
                    occurrence_number = {
                        "first": 1,
                        "second": 2,
                        "third": 3,
                        "fourth": 4,
                        "last": -1,
                    }[schedule.nth_weekday]
                    if occurrence_number == -1:
                        occurrence_date += relativedelta(
                            day=31,
                            weekday=weekday(weekday_number, -1),
                        )
                    else:
                        occurrence_date += relativedelta(
                            weekday=weekday(weekday_number, occurrence_number)
                        )
                else:
                    break
            elif frequency == "yearly":
                occurrence_date += relativedelta(years=interval)
            else:
                break
        except (OverflowError, ValueError):
            break
        iterations += 1

    return occurrences
