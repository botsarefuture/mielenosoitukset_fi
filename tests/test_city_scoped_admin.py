from copy import deepcopy

from bson import ObjectId

from mielenosoitukset_fi.users.models import User
from mielenosoitukset_fi.utils.cities import normalize_city_key
from tests.conftest import _client_for_user


def _create_scoped_admin(db, city_keys, permissions):
    user_id = ObjectId()
    user_doc = User.create_user(
        username="city-admin",
        password="CityPass1!",
        email="city-admin@example.test",
        displayname="City Admin",
    )
    user_doc.update(
        {
            "_id": user_id,
            "confirmed": True,
            "active": True,
            "role": "user",
            "global_admin": False,
            "global_permissions": [],
        }
    )
    db.users.insert_one(user_doc)
    db.admin_scope_grants.insert_one(
        {
            "user_id": user_id,
            "scope_type": "city",
            "scope_keys": city_keys,
            "role": "city_reviewer",
            "permissions": permissions,
        }
    )
    return user_id


def test_city_scoped_admin_dashboard_only_lists_assigned_cities(app, db, seeded_data):
    scoped_user_id = _create_scoped_admin(
        db,
        ["helsinki"],
        ["LIST_DEMOS", "VIEW_DEMO", "ACCEPT_DEMO"],
    )

    helsinki_demo = db.demonstrations.find_one({"_id": seeded_data["pending_demo_id"]})
    turku_demo = deepcopy(helsinki_demo)
    turku_demo["_id"] = ObjectId()
    turku_demo["title"] = "Turku Outside Scope"
    turku_demo["city"] = "Turku"
    turku_demo["city_key"] = normalize_city_key("Turku")
    turku_demo["slug"] = "turku-outside-scope"
    turku_demo["editors"] = []
    db.demonstrations.insert_one(turku_demo)

    client = _client_for_user(app, scoped_user_id)
    response = client.get("/admin/demo/")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Pending Demonstration" in page
    assert "Turku Outside Scope" not in page


def test_city_scoped_admin_can_approve_only_assigned_city(app, db, seeded_data):
    scoped_user_id = _create_scoped_admin(
        db,
        ["helsinki"],
        ["LIST_DEMOS", "VIEW_DEMO", "ACCEPT_DEMO"],
    )

    helsinki_demo_id = seeded_data["pending_demo_id"]
    helsinki_demo = db.demonstrations.find_one({"_id": helsinki_demo_id})
    turku_demo = deepcopy(helsinki_demo)
    turku_demo_id = ObjectId()
    turku_demo["_id"] = turku_demo_id
    turku_demo["title"] = "Turku Approval Denied"
    turku_demo["city"] = "Turku"
    turku_demo["city_key"] = normalize_city_key("Turku")
    turku_demo["slug"] = "turku-approval-denied"
    turku_demo["approved"] = False
    turku_demo["editors"] = []
    db.demonstrations.insert_one(turku_demo)

    client = _client_for_user(app, scoped_user_id)

    allowed = client.post(f"/api/admin/demo/{helsinki_demo_id}/approve")
    denied = client.post(f"/api/admin/demo/{turku_demo_id}/approve")

    assert allowed.status_code == 200
    assert allowed.get_json()["success"] is True
    assert db.demonstrations.find_one({"_id": helsinki_demo_id})["approved"] is True

    assert denied.status_code == 403
    assert db.demonstrations.find_one({"_id": turku_demo_id})["approved"] is False
