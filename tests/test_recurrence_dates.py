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


def test_recurrence_preview_aborts_stale_request_before_empty_date_return():
    script = Path(
        "mielenosoitukset_fi/static/js/admin_recurrence_preview.js"
    ).read_text(encoding="utf-8")

    refresh_start = script.index("async function refreshPreview()")
    abort_position = script.index("requestController?.abort()", refresh_start)
    empty_date_position = script.index('if (!query.get("date"))', refresh_start)

    assert abort_position < empty_date_position
    assert "if (requestController !== controller) return;" in script


def test_recurrence_dates_stop_one_year_ahead_even_with_a_distant_end_date():
    schedule = RepeatSchedule(frequency="weekly", interval=1, end_date="3100-01-05")

    dates = calculate_recurrence_dates(
        date(2026, 11, 6),
        schedule,
        max_occurrences=1000,
        today=date(2026, 11, 10),
        horizon_years=1,
    )

    assert dates[0] == date(2026, 11, 13)
    assert dates[-1] <= date(2027, 11, 10)
    assert len(dates) == 52

    # A worker that already ran past the horizon schedules nothing more.
    assert calculate_recurrence_dates(
        date(2026, 11, 6), schedule, date(2094, 3, 1), today=date(2026, 11, 10), horizon_years=1
    ) == []

    # Without a horizon (the admin preview) the series' own end date applies.
    assert len(calculate_recurrence_dates(
        date(2026, 11, 6), schedule, max_occurrences=200, today=date(2026, 11, 10)
    )) == 200
