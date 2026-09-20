from datetime import timedelta

from bson import ObjectId

from mielenosoitukset_fi.utils.time_utils import utcnow
from tests.conftest import _client_for_user


def _analytics_demo(index, *, editor_id=None):
    demo_id = ObjectId()
    demo = {
        "_id": demo_id,
        "title": f"Analytics demo {index:02d}",
        "date": (utcnow().date() + timedelta(days=30)).isoformat(),
        "approved": True,
        "editors": [editor_id] if editor_id else [],
        "organizers": [],
    }
    return demo_id, demo


def test_stats_collection_uses_deterministic_server_pagination(
    admin_client, db
):
    db.analytics.delete_many({})
    demos = [_analytics_demo(index) for index in range(45)]
    db.demonstrations.insert_many([demo for _, demo in demos])
    db.analytics.insert_many(
        [
            {
                "_id": ObjectId(),
                "demo_id": demo_id,
                "timestamp": utcnow(),
                "session_id": f"stats-{index:02d}",
            }
            for index, (demo_id, _) in enumerate(demos)
        ]
    )

    first = admin_client.get("/admin/stats?include_past=1&page=1&per_page=20")
    second = admin_client.get("/admin/stats?include_past=1&page=2&per_page=20")

    assert first.status_code == 200
    assert second.status_code == 200
    first_page = first.get_data(as_text=True)
    second_page = second.get_data(as_text=True)
    assert "Analytics demo 00" in first_page
    assert "Analytics demo 19" in first_page
    assert "Analytics demo 20" not in first_page
    assert "Analytics demo 19" not in second_page
    assert "Analytics demo 20" in second_page
    assert "Analytics demo 39" in second_page
    assert "Näytetään 21–40 / 45 mielenosoituksesta" in second_page
    assert "include_past=1" in second_page
    assert "per_page=20" in second_page


def test_scoped_analytics_viewer_only_sees_allowed_demo_counts(
    app, db, seeded_data
):
    db.users.update_one(
        {"_id": seeded_data["user_id"]},
        {"$set": {"role": "admin", "global_admin": False}},
    )
    membership = db.memberships.find_one(
        {
            "user_id": seeded_data["user_id"],
            "organization_id": seeded_data["org_id"],
        }
    )
    permissions = list(membership.get("permissions", []))
    permissions.append("VIEW_ANALYTICS")
    db.memberships.update_one(
        {"_id": membership["_id"]},
        {"$set": {"permissions": permissions}},
    )

    allowed_id, allowed = _analytics_demo(90, editor_id=seeded_data["user_id"])
    hidden_id, hidden = _analytics_demo(91)
    db.demonstrations.insert_many([allowed, hidden])
    db.analytics.insert_many(
        [
            {"_id": ObjectId(), "demo_id": allowed_id, "timestamp": utcnow()},
            {"_id": ObjectId(), "demo_id": hidden_id, "timestamp": utcnow()},
        ]
    )

    client = _client_for_user(app, seeded_data["user_id"])
    response = client.get("/admin/stats?include_past=1")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Analytics demo 90" in page
    assert "Analytics demo 91" not in page
    assert "Kaikki tilit" not in page
    assert "Yhteisöä ja ryhmää" not in page
    assert 'id="matomo-link"' not in page
    payload = client.get(
        "/admin/api/stats/summary?include_past=1"
    ).get_json()
    row_ids = {row["id"] for row in payload["analytics"]["rows"]}
    assert str(allowed_id) in row_ids
    assert str(hidden_id) not in row_ids
    assert payload["summary"]["total_users"] is None
    assert client.get("/admin/api/stats/matomo-live").status_code == 403
    assert client.get("/admin/analytics/overall_24h").status_code == 403


def test_demo_analytics_detail_requires_scoped_permission(
    app, db, seeded_data
):
    db.users.update_one(
        {"_id": seeded_data["user_id"]},
        {"$set": {"role": "admin", "global_admin": False}},
    )
    membership = db.memberships.find_one(
        {
            "user_id": seeded_data["user_id"],
            "organization_id": seeded_data["org_id"],
        }
    )
    db.memberships.update_one(
        {"_id": membership["_id"]},
        {"$addToSet": {"permissions": "VIEW_ANALYTICS"}},
    )
    hidden_id, hidden = _analytics_demo(92)
    db.demonstrations.insert_one(hidden)
    db.d_analytics.insert_one({"_id": hidden_id, "analytics": {}})

    response = _client_for_user(app, seeded_data["user_id"]).get(
        f"/admin/per_demo_analytics/{hidden_id}"
    )

    assert response.status_code == 403
