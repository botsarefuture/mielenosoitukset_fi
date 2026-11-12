from datetime import UTC, datetime, timedelta
from inspect import unwrap

from bson import ObjectId
import pytest

from tests.conftest import _allow_local_requests, _client_for_user
from tests.test_city_scoped_admin import _create_scoped_admin
from mielenosoitukset_fi.users.models import User
from mielenosoitukset_fi.utils.city_review_dashboard import city_review_queue

NOW = datetime(2026, 10, 24, 12, tzinfo=UTC)


def _pending(db, title, *, deadline=None, **changes):
    doc = {
        "_id": ObjectId(), "title": title, "city": "Helsinki", "city_key": "helsinki",
        "approved": False, "rejected": False, "cancelled": False,
        "city_assignment": {"review_deadline_at": deadline or NOW.replace(tzinfo=None) + timedelta(hours=24)},
        **changes,
    }
    db.demonstrations.insert_one(doc)
    return doc["_id"]


@pytest.mark.parametrize("locale,heading", [("fi", "Kaupunkiadminin käsittelyjono"), ("en", "City review queue"), ("sv", "Städernas granskningskö")])
def test_approval_only_city_dashboard_is_scoped_and_has_usable_review_links(app, db, seeded_data, monkeypatch, locale, heading):
    monkeypatch.setitem(app.config, "BABEL_PUBLIC_LOCALES", ["fi", "en", "sv"])
    monkeypatch.setitem(unwrap(app.view_functions["admin.admin_dashboard"]).__globals__, "utcnow", lambda: NOW.replace(tzinfo=None))
    user_id = _create_scoped_admin(db, ["helsinki"], ["ACCEPT_DEMO"])
    demo_id = _pending(db, "Allowed review")
    _pending(db, "Other city secret", city="Turku", city_key="turku")
    _pending(db, "Conflicting city secret", city="Helsinki", city_key="turku")
    _pending(db, "Already resolved", approved=True)
    client = _client_for_user(app, user_id)
    with client.session_transaction() as session:
        session["locale"] = locale
    response = client.get("/admin/dashboard")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert heading in html
    if locale == "en":
        assert "Awaiting review" in html and "Actions" in html
    elif locale == "sv":
        assert "Väntar på granskning" in html and "Åtgärder" in html
    assert "Allowed review" in html
    assert "Other city secret" not in html and "Conflicting city secret" not in html
    assert "Already resolved" not in html
    assert 'href="/admin/demo/review/' + str(demo_id) + '"' in html
    assert client.get(f"/admin/demo/review/{demo_id}").status_code == 200
    assert 'id="stat-users-total"' not in html
    assert client.get("/admin/dashboard/data").status_code == 403


def test_queue_orders_authoritative_deadlines_and_preserves_unknowns(app, db, seeded_data, monkeypatch):
    user_id = _create_scoped_admin(db, ["helsinki"], ["ACCEPT_DEMO"])
    late = _pending(db, "Later", deadline=NOW.replace(tzinfo=None) + timedelta(hours=48))
    early = _pending(db, "Earlier", deadline=NOW.replace(tzinfo=None) + timedelta(hours=1))
    legacy = _pending(db, "Legacy", city_assignment={"assigned_at": NOW.replace(tzinfo=None)})
    unknown = _pending(db, "Unknown", city_assignment={"review_deadline_at": None, "assigned_at": NOW.replace(tzinfo=None)})
    monkeypatch.setitem(app.config, "CITY_ASSIGNMENT_ESCALATION_HOURS", 72)
    with app.app_context():
        queue = city_review_queue(db, User.from_OID(user_id), 1, NOW)
    assert [row["id"] for row in queue["rows"]] == [str(early), str(late), str(legacy), str(unknown)]
    assert queue["rows"][0]["remaining_minutes"] == 60
    assert queue["rows"][1]["remaining_minutes"] == 48 * 60
    assert queue["rows"][2]["remaining_minutes"] == 72 * 60
    assert queue["rows"][3]["state"] == "unknown"
    assert queue["rows"][3]["deadline_iso"] is None
    assert "review_deadline_at" not in db.demonstrations.find_one({"_id": legacy})["city_assignment"]


def test_queue_pagination_is_bounded_stable_and_permission_specific(app, db, seeded_data):
    user_id = _create_scoped_admin(db, ["helsinki"], ["LIST_DEMOS"])
    ids = [_pending(db, f"Queue {number}") for number in range(22)]
    with app.app_context():
        user = User.from_OID(user_id)
        first = city_review_queue(db, user, 1, NOW)
        second = city_review_queue(db, user, 2, NOW)
        excessive = city_review_queue(db, user, "600000", NOW)
    assert first["total"] == second["total"] == 22
    assert [row["id"] for row in first["rows"] + second["rows"]] == [str(value) for value in ids]
    assert first["first"] == 1 and first["last"] == 20
    assert second["first"] == 21 and second["last"] == 22
    assert excessive == second
    assert not any(row["can_review"] or row["can_view"] for row in first["rows"])


def test_dashboard_states_are_explicit_and_get_never_resets_assignment(app, db, seeded_data, monkeypatch):
    monkeypatch.setitem(unwrap(app.view_functions["admin.admin_dashboard"]).__globals__, "utcnow", lambda: NOW.replace(tzinfo=None))
    user_id = _create_scoped_admin(db, ["helsinki"], ["ACCEPT_DEMO"])
    _pending(db, "Overdue", deadline=NOW.replace(tzinfo=None) - timedelta(seconds=1))
    _pending(db, "Escalated", city_assignment={"escalated": True, "review_deadline_at": NOW.replace(tzinfo=None)})
    _pending(db, "Unknown", city_assignment={"review_deadline_at": "invalid"})
    before = list(db.demonstrations.find({"city_assignment": {"$exists": True}}).sort("_id", 1))
    client = _client_for_user(app, user_id)
    html = client.get("/admin/dashboard").get_data(as_text=True)
    assert "odottaa siirtoa kansalliselle tiimille" in html
    assert "Siirretty kansalliselle tiimille" in html
    assert "Määräaika vaatii tarkistuksen" in html
    assert list(db.demonstrations.find({"city_assignment": {"$exists": True}}).sort("_id", 1)) == before


@pytest.mark.parametrize("width,theme", [(390, "light"), (1440, "dark")])
def test_city_queue_has_nojs_deadline_and_accessible_minute_clock(app, db, seeded_data, live_server, browser_page, width, theme):
    user_id = _create_scoped_admin(db, ["helsinki"], ["ACCEPT_DEMO"])
    _pending(db, "Deadline preview", deadline=datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=3))
    cookie = app.session_interface.get_signing_serializer(app).dumps({"_user_id": str(user_id), "_fresh": True})
    browser_page.context.add_cookies([{"name": app.config.get("SESSION_COOKIE_NAME", "session"), "value": cookie, "url": live_server}])
    browser_page.set_viewport_size({"width": width, "height": 1000})
    browser_page.add_init_script(f"localStorage.setItem('theme', '{theme}')")
    browser_page.add_init_script("Date.now = () => Date.parse('2099-01-01T00:00:00Z')")
    browser_page.goto(f"{live_server}/admin/dashboard", wait_until="domcontentloaded")
    assert browser_page.locator("time[datetime]").is_visible()
    assert browser_page.locator("[data-deadline]").get_attribute("aria-hidden") == "true"
    assert "Käsittelyaikaa jäljellä" in browser_page.locator("[data-deadline]").inner_text()
    assert browser_page.evaluate("getComputedStyle(document.documentElement).colorScheme") == theme
    assert browser_page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    for selector in ("time[datetime]", 'a[href*="/admin/demo/review/"]'):
        bounds = browser_page.locator(selector).bounding_box()
        assert bounds["x"] >= 0 and bounds["x"] + bounds["width"] <= width + 1
    assert "EET" in browser_page.locator("time").inner_text() or "EEST" in browser_page.locator("time").inner_text()
    browser_page.screenshot(path=f"/tmp/moso-city-queue-{width}-{theme}.png", full_page=True)
    with browser_page.context.browser.new_context(java_script_enabled=False, viewport={"width": width, "height": 1000}) as nojs:
        nojs.route("**/*", _allow_local_requests)
        nojs.add_cookies(browser_page.context.cookies())
        fallback = nojs.new_page()
        fallback.goto(f"{live_server}/admin/dashboard", wait_until="domcontentloaded")
        assert fallback.locator("time[datetime]").is_visible()
        assert fallback.locator('a[href*="/admin/demo/review/"]').is_visible()
    browser_page.evaluate("document.querySelector('[data-admin-deadlines]').dataset.serverNow = '2099-01-01T00:00:00Z'")
    browser_page.add_script_tag(url=f"{live_server}/static/js/admin_deadlines.js")
    assert "Määräaika päättynyt" in browser_page.locator("[data-deadline]").inner_text()
