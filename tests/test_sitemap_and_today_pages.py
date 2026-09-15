import xml.etree.ElementTree as ET
from datetime import date

from flask import url_for


def _sitemap_locs(response):
    root = ET.fromstring(response.data)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return {loc.text for loc in root.findall(".//sm:loc", ns)}


def test_sitemap_includes_public_city_org_tag_and_today_pages(app, db, seeded_data):
    response = app.test_client().get("/sitemap.xml", base_url="https://example.test")

    assert response.status_code == 200
    locs = _sitemap_locs(response)

    with app.test_request_context(base_url="https://example.test"):
        expected_urls = {
            url_for("cities", _external=True),
            url_for("today_demos", _external=True),
            url_for("city_demos", city="helsinki", _external=True),
            url_for("today_city_demos", city="helsinki", _external=True),
            url_for("org", org_id=str(seeded_data["org_id"]), _external=True),
            url_for("tag_detail", tag_name="test-tag", _external=True),
            url_for("public_guides", _external=True),
            url_for("api_docs", _external=True),
            url_for("pride_nakyvaksi", _external=True),
        }

    assert expected_urls <= locs
    assert not any("/api/v1/" in loc for loc in locs)
    assert not any("/save_suggestion" in loc for loc in locs)


def test_cities_page_links_to_today_and_future_city_views(app, seeded_data):
    response = app.test_client().get("/cities")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Mielenosoitukset kaupungeittain" in page
    assert "/mielenosoitukset-tanaan" in page
    assert "/city/helsinki/tanaan" in page
    assert "/city/helsinki" in page


def test_today_pages_render_finland_and_city_specific_demos(app, db, seeded_data):
    today = date.today().isoformat()
    db.demonstrations.update_one(
        {"_id": seeded_data["demo_id"]},
        {"$set": {"date": today, "start_time": "12:30", "city": "Helsinki", "city_key": "helsinki"}},
    )

    client = app.test_client()
    finland_response = client.get("/mielenosoitukset-tanaan")
    city_response = client.get("/city/helsinki/tanaan")

    assert finland_response.status_code == 200
    assert city_response.status_code == 200

    finland_page = finland_response.get_data(as_text=True)
    city_page = city_response.get_data(as_text=True)
    assert "Mielenosoitukset Suomessa tänään" in finland_page
    assert "Climate March Helsinki" in finland_page
    assert "Mielenosoitukset Helsingissä tänään" in city_page
    assert "Climate March Helsinki" in city_page
    assert "12:30" in city_page
