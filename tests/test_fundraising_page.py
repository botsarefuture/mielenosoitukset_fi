"""The public fundraising preview must not imply donations are already open."""

from datetime import date

import pytest

from mielenosoitukset_fi.utils.fundraising import fundraising_details


@pytest.fixture(autouse=True)
def published_campaign(db, seeded_data):
    """Existing public-content checks exercise the explicitly published state."""
    db.campaign_settings.update_one(
        {"_id": "public_pages"}, {"$set": {"published": True}}, upsert=True
    )
    yield
    db.campaign_settings.delete_one({"_id": "public_pages"})



def _confirmed_plan():
    return {
        "publication_state": "active", "details_confirmed": True,
        "start_date": "2026-11-15", "end_date": "2027-02-15",
        "organizer": "Example organizer", "collection_number": "EXAMPLE-NOT-REAL",
        "recipient": "Example recipient", "iban": "EXAMPLE-NOT-A-BANK-ACCOUNT",
        "payment_url": "", "reference": "123",
        "mobilepay_links": [],
    }


def test_fundraising_preview_is_public_and_has_no_payment_instructions(client):
    response = client.get("/keräys")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "2 500 €" in page
    assert "Valmistelussa" in page
    assert "Lahjoittaminen ei ole vielä avoinna" in page
    assert 'datetime="2026-11-15"' in page
    assert 'datetime="2027-02-15"' in page
    assert "jatkuvuuden turvaamiseen" in page
    assert 'href="/contact"' in page
    assert '<article class="public-content" lang="fi">' in page
    assert "MobilePay 1" in page and "MobilePay 2" in page
    assert 'name="iban"' not in page and 'type="submit"' not in page


@pytest.mark.parametrize("changes,today,allowed", [
    ({}, date(2026, 11, 15), True),
    ({}, date(2027, 2, 15), True),
    ({}, date(2026, 11, 14), False),
    ({}, date(2027, 2, 16), False),
    ({"publication_state": "preparation"}, date(2026, 12, 1), False),
    ({"details_confirmed": False}, date(2026, 12, 1), False),
    ({"collection_number": ""}, date(2026, 12, 1), False),
    ({"organizer": ""}, date(2026, 12, 1), False),
    ({"start_date": "invalid"}, date(2026, 12, 1), False),
    ({"end_date": "2026-10-01"}, date(2026, 12, 1), False),
    ({"iban": "", "payment_url": "https://example.test/donate"}, date(2026, 12, 1), True),
    ({"iban": "", "payment_url": "javascript:alert(1)", "mobilepay_links": []}, date(2026, 12, 1), False),
    ({"iban": "", "payment_url": "", "mobilepay_links": [{"label": "MobilePay 1", "url": "https://qr.mobilepay.fi/box/example-one/pay-in"}]}, date(2026, 12, 1), True),
])
def test_donations_require_complete_confirmed_active_details_within_dates(changes, today, allowed):
    plan = _confirmed_plan() | changes
    assert fundraising_details(plan, today=today)["can_donate"] is allowed


def test_confirmed_donation_details_render_escaped_and_close_after_end(client, monkeypatch):
    plan = _confirmed_plan() | {
        "organizer": "Example <script>unsafe</script>", "payment_url": "https://example.test/donate",
        "mobilepay_links": [
            {"label": "MobilePay 1", "url": "https://qr.mobilepay.fi/box/example-one/pay-in"},
            {"label": "MobilePay 2", "url": "https://qr.mobilepay.fi/box/example-two/pay-in"},
        ],
    }
    route_globals = client.application.view_functions["fundraising"].__wrapped__.__globals__
    monkeypatch.setitem(route_globals, "fundraising_details", lambda: fundraising_details(plan, today=date(2026, 12, 1)))
    page = client.get("/keräys").get_data(as_text=True)
    assert "Näin lahjoitat" in page and 'href="https://example.test/donate"' in page
    assert "EXAMPLE-NOT-A-BANK-ACCOUNT" in page
    assert "Example &lt;script&gt;unsafe&lt;/script&gt;" in page
    assert "Example <script>" not in page
    for link in plan["mobilepay_links"]:
        assert f'href="{link["url"]}"' in page
    monkeypatch.setitem(route_globals, "fundraising_details", lambda: fundraising_details(plan, today=date(2027, 2, 16)))
    page = client.get("/keräys").get_data(as_text=True)
    assert "Lahjoittaminen on suljettu" in page
    assert "EXAMPLE-NOT-A-BANK-ACCOUNT" not in page
    assert 'href="https://example.test/donate"' not in page
    assert "https://qr.mobilepay.fi/box/" not in page
    plan["publication_state"] = "preparation"
    page = client.get("/keräys").get_data(as_text=True)
    assert "Valmistelussa" in page and "Suunnitteilla oleva pienkeräys" in page


def test_header_promotion_is_opt_in_and_campaign_preserves_signup_hooks(client, monkeypatch):
    assert 'class="fundraising-header-link"' not in client.get("/info").get_data(as_text=True)
    route_globals = client.application.view_functions["fundraising"].__wrapped__.__globals__
    monkeypatch.setitem(route_globals, "fundraising_details", lambda: fundraising_details({"show_header_link": True}))
    page = client.get("/info").get_data(as_text=True)
    assert 'class="fundraising-header-link"' in page
    assert 'href="/ker%C3%A4ys"' in page
    campaign = client.get("/kampanja/")
    assert campaign.status_code == 200
    page = campaign.get_data(as_text=True)
    assert 'id="kerays"' in page and 'href="/ker%C3%A4ys"' in page
    assert 'id="volunteer-form"' in page and 'id="newsletter-form"' in page
    assert "Kampanja alkoi 1.3.2026" not in page
    assert 'id="materiaalitavoitteet"' in page and "25 000" in page
    assert "1 889,94" in page and "eivät vielä toteutuneita" in page


@pytest.mark.parametrize("url", [
    "javascript:alert(1)", "https://user:pass@example.test/pay",
    "https://example.test:invalid/pay", "https://example.test\\evil/pay",
    "https://example.test/ pay", "https://example.test/\npay",
])
def test_unsafe_payment_urls_never_enable_donations(url):
    plan = _confirmed_plan() | {
        "recipient": "", "iban": "", "payment_url": url,
        "mobilepay_links": [{"label": "MobilePay", "url": url}],
    }
    details = fundraising_details(plan, today=date(2026, 12, 1))
    assert not details["can_donate"]
    assert not details["payment_url"]
    assert not details["mobilepay_links"][0]["url"]


def test_planned_dates_do_not_replace_confirmed_dates_or_explicit_opening():
    plan = _confirmed_plan() | {
        "start_date": "", "end_date": "",
        "planned_start_date": "2026-11-15", "planned_end_date": "2027-02-15",
    }
    details = fundraising_details(plan, today=date(2026, 12, 1))
    assert details["is_preparation"] and not details["can_donate"]
    assert details["display_start_date"] == date(2026, 11, 15)
    plan = _confirmed_plan() | {"publication_state": "closed"}
    assert not fundraising_details(plan, today=date(2026, 12, 1))["can_donate"]
