import xml.etree.ElementTree as ET
from datetime import date, timedelta

from bson import ObjectId

from flask import url_for


def _sitemap_locs(response):
    root = ET.fromstring(response.data)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return {loc.text for loc in root.findall(".//sm:loc", ns)}


def _sitemap_entries(response):
    root = ET.fromstring(response.data)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return {
        url.find("sm:loc", ns).text: url.findtext("sm:priority", namespaces=ns)
        for url in root.findall("sm:url", ns)
    }


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


def test_sitemap_demo_priority_is_highest_for_date_closest_to_today(app, db, seeded_data):
    today = date.today()
    near_id = seeded_data["demo_id"]
    far_id = ObjectId()
    db.demonstrations.update_one(
        {"_id": near_id},
        {"$set": {"date": (today + timedelta(days=1)).isoformat()}},
    )
    source = db.demonstrations.find_one({"_id": near_id})
    source.update(
        {
            "_id": far_id,
            "slug": "far-future-priority-demo",
            "running_number": 99001,
            "date": (today + timedelta(days=500)).isoformat(),
        }
    )
    db.demonstrations.insert_one(source)

    response = app.test_client().get("/sitemap.xml", base_url="https://example.test")
    entries = _sitemap_entries(response)

    with app.test_request_context(base_url="https://example.test"):
        near_url = url_for("demonstration_detail", demo_id="climate-march-helsinki", _external=True)
        far_url = url_for("demonstration_detail", demo_id="far-future-priority-demo", _external=True)

    assert response.status_code == 200
    assert float(entries[near_url]) > float(entries[far_url])


def test_demo_after_sitemap_horizon_is_noindex_and_excluded(app, db, seeded_data):
    beyond_horizon = (date.today() + timedelta(days=(365 * 2) + 1)).isoformat()
    db.demonstrations.update_one(
        {"_id": seeded_data["demo_id"]},
        {"$set": {"date": beyond_horizon}},
    )

    client = app.test_client()
    detail_response = client.get("/demonstration/climate-march-helsinki")
    sitemap_response = client.get("/sitemap.xml", base_url="https://example.test")
    page = detail_response.get_data(as_text=True)

    assert detail_response.status_code == 200
    assert page.count('name="robots"') == 1
    assert '<meta name="robots" content="noindex, follow"' in page
    assert detail_response.headers["X-Robots-Tag"] == "noindex, follow"
    assert not any("climate-march-helsinki" in loc for loc in _sitemap_locs(sitemap_response))

    cached_response = client.get("/demonstration/climate-march-helsinki")
    assert cached_response.headers["X-Robots-Tag"] == "noindex, follow"
    assert '<meta name="robots" content="noindex, follow"' in cached_response.get_data(
        as_text=True
    )


def test_demo_at_sitemap_horizon_remains_indexable(app, db, seeded_data):
    horizon = (date.today() + timedelta(days=365 * 2)).isoformat()
    db.demonstrations.update_one(
        {"_id": seeded_data["demo_id"]},
        {"$set": {"date": horizon}},
    )

    client = app.test_client()
    detail_response = client.get("/demonstration/climate-march-helsinki")
    sitemap_response = client.get("/sitemap.xml", base_url="https://example.test")
    page = detail_response.get_data(as_text=True)

    assert detail_response.status_code == 200
    assert page.count('name="robots"') == 1
    assert '<meta name="robots" content="index, follow"' in page
    assert "X-Robots-Tag" not in detail_response.headers
    assert any("climate-march-helsinki" in loc for loc in _sitemap_locs(sitemap_response))


def test_historical_demo_outside_sitemap_remains_indexable(app, db, seeded_data):
    historical_date = (date.today() - timedelta(days=366)).isoformat()
    db.demonstrations.update_one(
        {"_id": seeded_data["demo_id"]},
        {"$set": {"date": historical_date}},
    )

    client = app.test_client()
    detail_response = client.get("/demonstration/climate-march-helsinki")
    sitemap_response = client.get("/sitemap.xml", base_url="https://example.test")

    assert '<meta name="robots" content="index, follow"' in detail_response.get_data(
        as_text=True
    )
    assert "X-Robots-Tag" not in detail_response.headers
    assert not any("climate-march-helsinki" in loc for loc in _sitemap_locs(sitemap_response))


def test_invalid_demo_date_is_never_emitted_in_sitemap(app, db, seeded_data):
    db.demonstrations.update_one(
        {"_id": seeded_data["demo_id"]},
        {"$set": {"date": f"{date.today().year + 1}-02-99"}},
    )

    client = app.test_client()
    sitemap_response = client.get("/sitemap.xml", base_url="https://example.test")

    assert not any("climate-march-helsinki" in loc for loc in _sitemap_locs(sitemap_response))


def test_detail_cache_varies_when_date_crosses_noindex_boundary(app, db, seeded_data):
    client = app.test_client()
    first_response = client.get("/demonstration/climate-march-helsinki")
    assert '<meta name="robots" content="index, follow"' in first_response.get_data(
        as_text=True
    )

    db.demonstrations.update_one(
        {"_id": seeded_data["demo_id"]},
        {"$set": {"date": (date.today() + timedelta(days=(365 * 2) + 1)).isoformat()}},
    )
    changed_response = client.get("/demonstration/climate-march-helsinki")

    assert '<meta name="robots" content="noindex, follow"' in changed_response.get_data(
        as_text=True
    )
    assert changed_response.headers["X-Robots-Tag"] == "noindex, follow"


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
