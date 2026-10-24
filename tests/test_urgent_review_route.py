from datetime import UTC, datetime
import re

from bson import ObjectId
import pytest

from tests.conftest import _client_for_user
from tests.test_city_scoped_admin import _create_scoped_admin
from mielenosoitukset_fi.utils.urgent_review_alerts import build_urgent_review_alert


def _review_client(app, db, permissions=("ACCEPT_DEMO",), city="helsinki"):
    return _client_for_user(app, _create_scoped_admin(db, [city], list(permissions)))


def test_alert_link_is_usable_with_only_scoped_approval_permission(app, db, seeded_data):
    demo_id = seeded_data["pending_demo_id"]
    private = "private-review-sentinel"
    db.demonstrations.update_one({"_id": demo_id}, {"$set": {
        "city": "Helsinki", "city_key": "helsinki", "date": "2026-10-24",
        "start_time": "15:00", "submitter_email": private, "token": private,
        "description": '<script>alert("unsafe")</script>\nVisible content',
    }})
    demo = db.demonstrations.find_one({"_id": demo_id})
    snapshot = build_urgent_review_alert(demo, datetime(2026, 10, 23, 12, tzinfo=UTC))
    path = re.search(r'href="https://mielenosoitukset.fi([^"]+)"', snapshot["text"])[1]
    client = _review_client(app, db)
    response = client.get(path)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'class="admin-page-hero__content"' in html
    assert 'name="decision"' in html
    assert "Visible content" in html
    assert '<script>alert("unsafe")</script>' not in html
    assert "&lt;script&gt;" in html
    assert private not in html
    assert client.get(f"/admin/demo/edit_demo/{demo_id}").status_code == 403
    assert client.get(f"/admin/demo/command-center/{demo_id}").status_code == 403
    assert app.test_client().get(path).status_code == 302


@pytest.mark.parametrize("permissions,city", [(["ACCEPT_DEMO"], "turku"), (["VIEW_DEMO"], "helsinki")])
def test_review_rejects_other_city_and_non_approvers(app, db, seeded_data, permissions, city):
    demo_id = seeded_data["pending_demo_id"]
    db.demonstrations.update_one({"_id": demo_id}, {"$set": {"city": "Helsinki", "city_key": "helsinki"}})
    client = _review_client(app, db, permissions, city)
    before = db.demonstrations.find_one({"_id": demo_id})
    assert client.get(f"/admin/demo/review/{demo_id}").status_code == 403
    assert client.post(f"/admin/demo/review/{demo_id}", data={"decision": "approved"}).status_code == 403
    assert db.demonstrations.find_one({"_id": demo_id}) == before


@pytest.mark.parametrize("decision", ["approved", "rejected"])
def test_review_decision_uses_canonical_service_and_cleared_assignment_snapshot(app, db, seeded_data, decision):
    demo_id = seeded_data["pending_demo_id"]
    db.demonstrations.update_one({"_id": demo_id}, {"$set": {
        "city": "Helsinki", "city_key": "helsinki",
        "city_assignment": {"escalated": False},
    }})
    client = _review_client(app, db)
    path = f"/admin/demo/review/{demo_id}"
    page = client.get(path).get_data(as_text=True)
    token = re.search(r'name="csrf_token" value="([^"]+)"', page)[1]
    assert client.post(path, data={"decision": decision}).status_code == 403
    assert client.post(path, data={"decision": "invalid", "csrf_token": token}).status_code == 400
    assert not db.demonstrations.find_one({"_id": demo_id}).get("approved")
    assert client.post(path, data={"decision": decision, "csrf_token": token}).status_code == 302
    updated = db.demonstrations.find_one({"_id": demo_id})
    assert updated["approved"] is (decision == "approved")
    assert updated["rejected"] is (decision == "rejected")
    assert updated["moderation_decision"]["source"] == "admin_review"
    assert not updated.get("city_assignment")
    snapshot = build_urgent_review_alert(updated, datetime(2026, 10, 23, tzinfo=UTC), has_message=True)
    assert snapshot["responsibility"] is None
    assert "Vastuu:" not in snapshot["text"]
    assert 'name="decision"' not in client.get(path).get_data(as_text=True)
    before = updated["moderation_decision"]["id"]
    assert client.post(path, data={"decision": decision, "csrf_token": token}).status_code == 302
    assert db.demonstrations.find_one({"_id": demo_id})["moderation_decision"]["id"] == before


def test_review_handles_missing_identity_and_cancelled_posts(app, db, seeded_data, admin_client):
    client = _review_client(app, db)
    assert client.get("/admin/demo/review/not-an-id").status_code == 403
    assert client.get(f"/admin/demo/review/{ObjectId()}").status_code == 403
    # Global admins bypass the scope decorator, so route validation must still
    # reject malformed identities instead of leaking an uncaught ValueError.
    assert admin_client.get("/admin/demo/review/not-an-id").status_code == 400
    assert admin_client.get(f"/admin/demo/review/{ObjectId()}").status_code == 404
    demo_id = seeded_data["pending_demo_id"]
    db.demonstrations.update_one({"_id": demo_id}, {"$set": {
        "city": "Helsinki", "city_key": "helsinki", "cancelled": True,
    }})
    path = f"/admin/demo/review/{demo_id}"
    assert client.get(path).status_code == 200
    with client.session_transaction() as session:
        token = session["demo_edit_link_csrf_token"]
    assert client.post(path, data={"decision": "approved", "csrf_token": token}).status_code == 409
    assert not db.demonstrations.find_one({"_id": demo_id}).get("approved")


@pytest.mark.parametrize("width,theme", [(390, "light"), (390, "dark"), (1440, "light"), (1440, "dark")])
def test_review_uses_shared_responsive_theme_in_browser(app, db, seeded_data, live_server, browser_page, width, theme):
    demo_id = seeded_data["pending_demo_id"]
    user_id = _create_scoped_admin(db, ["helsinki"], ["ACCEPT_DEMO"])
    db.demonstrations.update_one({"_id": demo_id}, {"$set": {
        "city": "Helsinki", "city_key": "helsinki",
    }})
    cookie = app.session_interface.get_signing_serializer(app).dumps({"_user_id": str(user_id), "_fresh": True})
    browser_page.context.add_cookies([{"name": app.config.get("SESSION_COOKIE_NAME", "session"), "value": cookie, "url": live_server}])
    browser_page.set_viewport_size({"width": width, "height": 1000})
    browser_page.add_init_script(f"localStorage.setItem('theme', '{theme}')")
    browser_page.goto(f"{live_server}/admin/demo/review/{demo_id}", wait_until="networkidle")
    assert browser_page.evaluate("getComputedStyle(document.documentElement).colorScheme") == theme
    assert browser_page.locator(".admin-page-hero__content h1").is_visible()
    assert browser_page.locator('select[name="decision"]').is_visible()
    assert browser_page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    browser_page.locator('select[name="decision"]').focus()
    assert browser_page.locator('select[name="decision"]').evaluate("el => el === document.activeElement")
    browser_page.screenshot(path=f"/tmp/moso-urgent-review-{width}-{theme}.png", full_page=True)
