"""The fundraising bar settings come from the fundraising configuration and stay off by default."""
from mielenosoitukset_fi.utils.fundraising import fundraising_bar

BASE = {
    "publication_state": "active", "details_confirmed": True, "organizer": "Esimerkki ry", "collection_number": "RA/2026/1",
    "payment_url": "https://pay.example/lahjoita", "start_date": "2026-11-16", "end_date": "2027-02-15",
}


def test_bar_is_off_by_default_even_with_complete_details():
    assert fundraising_bar(BASE)["enabled"] is False
    assert fundraising_bar({**BASE, "show_bar": "yes"})["enabled"] is False
    assert fundraising_bar({})["enabled"] is False


def test_bar_uses_confirmed_dates_and_donations_open():
    bar = fundraising_bar({**BASE, "show_bar": True})
    assert bar == {"enabled": True, "start": "2026-11-16", "end": "2027-02-15", "donations_open": True}


def test_bar_announces_planned_dates_before_confirmation_and_never_claims_a_running_collection():
    bar = fundraising_bar({"show_bar": True, "publication_state": "preparation", "details_confirmed": False,
                           "planned_start_date": "2026-11-16", "planned_end_date": "2027-02-15"})
    assert bar["enabled"] is True and bar["start"] == "2026-11-16" and bar["donations_open"] is False
    closed = fundraising_bar({**BASE, "show_bar": True, "publication_state": "closed"})
    assert closed["donations_open"] is False


def test_bar_is_off_without_dates():
    assert fundraising_bar({"show_bar": True})["enabled"] is False
    assert fundraising_bar({"show_bar": True, "start_date": "bad", "end_date": "2027-02-15"})["enabled"] is False


def test_session_summary_carries_the_bar_settings_from_the_shipped_configuration(client):
    payload = client.get("/api/session").get_json()
    assert payload["fundraising_bar"]["enabled"] is True
    assert set(payload["fundraising_bar"]) == {"enabled", "start", "end", "donations_open"}


def test_shipped_configuration_announces_the_opening_but_hides_donation_details():
    from datetime import date

    from mielenosoitukset_fi.utils.fundraising import fundraising_details

    for day in (date(2026, 11, 14), date(2026, 11, 15)):
        bar = fundraising_bar(today=day)
        assert bar["enabled"] is True and bar["start"] == "2026-11-16" and bar["end"] == "2027-02-15"
        assert bar["donations_open"] is False
        assert fundraising_details(today=day)["can_donate"] is False
