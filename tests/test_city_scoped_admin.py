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
            "role": "city_admin",
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


def test_city_scoped_permission_does_not_satisfy_unscoped_route_gate(db):
    scoped_user_id = _create_scoped_admin(
        db,
        ["helsinki"],
        ["CREATE_DEMO"],
    )

    user = User.from_db(db.users.find_one({"_id": scoped_user_id}))

    assert user.has_scoped_permission(
        "CREATE_DEMO",
        scope_type="city",
        scope_key="helsinki",
    )
    assert user.has_permission("CREATE_DEMO") is False


def test_city_admin_gets_limited_organization_permissions(db):
    scoped_user_id = _create_scoped_admin(
        db,
        ["helsinki"],
        ["LIST_DEMOS", "VIEW_DEMO"],
    )
    user = User.from_db(db.users.find_one({"_id": scoped_user_id}))

    assert user.role == "city_admin"
    assert user.has_permission("LIST_ORGANIZATIONS")
    assert user.has_permission("VIEW_ORGANIZATION", ObjectId())
    assert user.has_permission("CREATE_ORGANIZATION")
    assert user.has_permission("EDIT_ORGANIZATION", ObjectId())
    assert user.has_permission("INVITE_TO_ORGANIZATION", ObjectId())
    assert not user.has_permission("DELETE_ORGANIZATION", ObjectId())


def test_city_admin_can_create_and_edit_but_cannot_verify_organization(
    app, db, seeded_data
):
    scoped_user_id = _create_scoped_admin(
        db,
        ["helsinki"],
        ["LIST_DEMOS", "VIEW_DEMO"],
    )
    client = _client_for_user(app, scoped_user_id)

    dashboard = client.get("/admin/organization/")
    assert dashboard.status_code == 200
    assert "Test Organization" in dashboard.get_data(as_text=True)

    create_response = client.post(
        "/admin/organization/create",
        data={
            "name": "City Admin Organization",
            "description": "Created by a city admin.",
            "email": "city-org@example.test",
            "website": "https://city-org.example.test",
        },
        headers={"Referer": "/admin/organization/"},
    )
    assert create_response.status_code == 302
    created = db.organizations.find_one({"name": "City Admin Organization"})
    assert created is not None
    assert created.get("verified", False) is False

    edit_response = client.post(
        f"/admin/organization/edit/{created['_id']}",
        data={
            "name": "City Admin Organization Updated",
            "description": "Updated by a city admin.",
            "email": "city-org@example.test",
            "website": "https://city-org.example.test",
            "verified": "on",
        },
        headers={"Referer": f"/admin/organization/edit/{created['_id']}"},
    )
    assert edit_response.status_code == 302
    updated = db.organizations.find_one({"_id": created["_id"]})
    assert updated["name"] == "City Admin Organization Updated"
    assert updated.get("verified", False) is False

    edit_page = client.get(f"/admin/organization/edit/{created['_id']}")
    assert edit_page.status_code == 200
    assert 'name="verified"' not in edit_page.get_data(as_text=True)


def test_city_admin_cannot_change_existing_verified_status(app, db, seeded_data):
    scoped_user_id = _create_scoped_admin(
        db,
        ["helsinki"],
        ["LIST_DEMOS", "VIEW_DEMO"],
    )
    client = _client_for_user(app, scoped_user_id)
    verified_org = db.organizations.find_one({"verified": True})

    response = client.post(
        f"/admin/organization/edit/{verified_org['_id']}",
        data={
            "name": verified_org["name"],
            "description": "City admin may edit content but not verification.",
            "email": verified_org["email"],
            "website": verified_org["website"],
        },
        headers={"Referer": f"/admin/organization/edit/{verified_org['_id']}"},
    )

    assert response.status_code == 302
    refreshed = db.organizations.find_one({"_id": verified_org["_id"]})
    assert refreshed["verified"] is True
    assert refreshed["description"] == "City admin may edit content but not verification."


def test_city_admin_cannot_invite_to_verified_organization(app, db, seeded_data):
    scoped_user_id = _create_scoped_admin(
        db,
        ["helsinki"],
        ["LIST_DEMOS", "VIEW_DEMO"],
    )
    client = _client_for_user(app, scoped_user_id)
    verified_org = db.organizations.find_one({"verified": True})

    response = client.post(
        "/admin/organization/invite",
        data={
            "organization_id": str(verified_org["_id"]),
            "invitee_email": "blocked-invite@example.test",
        },
    )

    assert response.status_code == 403
    refreshed = db.organizations.find_one({"_id": verified_org["_id"]})
    assert "blocked-invite@example.test" not in refreshed.get("invitations", [])

    api_response = client.post(
        "/admin/organization/api/set_invite_role/",
        json={
            "organization_id": str(verified_org["_id"]),
            "email": "api-bypass@example.test",
            "role": "member",
        },
    )
    assert api_response.status_code == 403
    refreshed = db.organizations.find_one({"_id": verified_org["_id"]})
    assert all(
        invite != "api-bypass@example.test"
        and not (isinstance(invite, dict) and invite.get("email") == "api-bypass@example.test")
        for invite in refreshed.get("invitations", [])
    )


def test_city_admin_can_invite_to_unverified_organization(
    app, db, seeded_data, monkeypatch
):
    from importlib import import_module

    admin_org_module = import_module("mielenosoitukset_fi.admin.admin_org_bp")
    scoped_user_id = _create_scoped_admin(
        db,
        ["helsinki"],
        ["LIST_DEMOS", "VIEW_DEMO"],
    )
    client = _client_for_user(app, scoped_user_id)
    unverified_org = db.organizations.find_one({"verified": False})
    monkeypatch.setattr(admin_org_module.email_sender, "queue_email", lambda **kwargs: None)

    response = client.post(
        "/admin/organization/invite",
        data={
            "organization_id": str(unverified_org["_id"]),
            "invitee_email": "allowed-invite@example.test",
        },
        headers={"Referer": f"/admin/organization/view/{unverified_org['_id']}"},
    )

    assert response.status_code == 302
    refreshed = db.organizations.find_one({"_id": unverified_org["_id"]})
    assert "allowed-invite@example.test" in refreshed.get("invitations", [])


def test_city_admin_dashboard_redirects_to_scoped_demo_view(app, db):
    scoped_user_id = _create_scoped_admin(
        db,
        ["helsinki"],
        ["LIST_DEMOS", "VIEW_DEMO"],
    )
    client = _client_for_user(app, scoped_user_id)

    response = client.get("/admin/dashboard")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/demo/")

    assert client.get("/admin/dashboard/data").status_code == 403
    assert client.get("/admin/dashboard/login-feed").status_code == 403
    assert client.post("/admin/dashboard/panic/activate").status_code == 403
    assert client.post("/admin/dashboard/cache/clear").status_code == 403


def test_edit_user_revokes_object_id_backed_city_scope_grant(app, db, seeded_data):
    scoped_user_id = _create_scoped_admin(
        db,
        ["helsinki"],
        ["LIST_DEMOS", "VIEW_DEMO"],
    )
    client = _client_for_user(app, seeded_data["admin_id"])

    response = client.post(
        f"/admin/user/edit_user/{scoped_user_id}",
        data={
            "username": "city-admin",
            "email": "city-admin@example.test",
            "role": "user",
            "confirmed": "on",
        },
    )

    assert response.status_code == 302
    grant = db.admin_scope_grants.find_one(
        {"user_id": scoped_user_id, "scope_type": "city"}
    )
    assert grant["revoked_at"] is not None
