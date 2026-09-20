from datetime import date
from pathlib import Path

from mielenosoitukset_fi.utils.classes.RepeatSchedule import RepeatSchedule
from mielenosoitukset_fi.utils.recurrence import calculate_recurrence_dates


def test_recurrence_dates_align_weekly_schedule_and_limit_output():
    schedule = RepeatSchedule(
        frequency="weekly",
        interval=2,
        weekday="friday",
        end_date="2026-03-31",
    )

    dates = calculate_recurrence_dates(
        date(2026, 1, 1),
        schedule,
        max_occurrences=4,
        today=date(2025, 1, 1),
    )

    assert dates == [
        date(2026, 1, 1),
        date(2026, 1, 9),
        date(2026, 1, 23),
        date(2026, 2, 6),
    ]


def test_recurrence_dates_honor_selected_day_of_month():
    schedule = RepeatSchedule(
        frequency="monthly",
        interval=1,
        monthly_option="day_of_month",
        day_of_month=15,
        end_date="2026-03-31",
    )

    dates = calculate_recurrence_dates(
        date(2026, 1, 1),
        schedule,
        today=date(2025, 1, 1),
    )

    assert dates == [date(2026, 1, 1), date(2026, 2, 15), date(2026, 3, 15)]


def test_recurrence_preview_script_uses_safe_dom_rendering():
    script = Path(
        "mielenosoitukset_fi/static/js/admin_recurrence_preview.js"
    ).read_text(encoding="utf-8")

    assert "textContent" in script
    assert "replaceChildren" in script
    assert "MutationObserver" in script
    assert "innerHTML" not in script
