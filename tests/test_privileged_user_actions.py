"""All user management entrypoints require scoped global delegation."""

import pytest
from types import SimpleNamespace
from bson import ObjectId
from mielenosoitukset_fi.admin.admin_user_bp import compare_user_levels
from tests.conftest import _client_for_user
from tests.test_city_scoped_admin import _create_organization_admin


def test_full_permission_actor_can_assign_global_role_with_legacy_base_role():
    from mielenosoitukset_fi.admin.admin_user_bp import _check_user_assignment
    actor = SimpleNamespace(_id=ObjectId(), role='admin', global_permissions=[],
                            has_full_permissions=lambda: True)
    target = SimpleNamespace(_id=ObjectId(), role='user', global_permissions=[])
    _check_user_assignment(actor, 'global_admin', [], target)


def _form(user, role="user"):
    return {
        "username": user["username"], "displayname": user.get("displayname") or user["username"],
        "email": user["email"], "role": role, "confirmed": "on",
    }


@pytest.mark.parametrize("route", ["edit_user", "save_user"])
def test_direct_user_edit_cannot_change_higher_role_target(admin_client, db, seeded_data, route):
    target = seeded_data["user_id"]
    db.users.update_one({"_id": target}, {"$set": {"role": "god"}})
    before = db.users.find_one({"_id": target})
    response = admin_client.post(f"/admin/user/{route}/{target}", data=_form(before))
    assert response.status_code == 403
    assert db.users.find_one({"_id": target}) == before


@pytest.mark.parametrize("route", ["edit_user", "save_user"])
def test_admin_cannot_self_promote_through_either_entrypoint(admin_client, db, seeded_data, route):
    target = seeded_data["admin_id"]
    before = db.users.find_one({"_id": target})
    response = admin_client.post(f"/admin/user/{route}/{target}", data=_form(before, role="god"))
    assert response.status_code == 403
    assert db.users.find_one({"_id": target}) == before


def test_restricted_editor_cannot_delegate_unowned_global_permission(app, db, seeded_data):
    actor = seeded_data["friend_id"]
    db.users.update_one({"_id": actor}, {"$set": {
        "role": "admin", "global_admin": False, "global_permissions": ["EDIT_USER"],
    }})
    target = seeded_data["user_id"]
    before = db.users.find_one({"_id": target})
    data = _form(before)
    data["permissions[global][]"] = ["DELETE_USER"]
    response = _client_for_user(app, actor).post(f"/admin/user/save_user/{target}", data=data)
    assert response.status_code == 403
    assert db.users.find_one({"_id": target}) == before


def test_restricted_editor_cannot_edit_globally_privileged_legacy_user(app, db, seeded_data):
    actor = seeded_data["friend_id"]
    db.users.update_one({"_id": actor}, {"$set": {
        "role": "admin", "global_admin": False, "global_permissions": ["EDIT_USER"],
    }})
    target = seeded_data["user_id"]
    db.users.update_one({"_id": target}, {"$set": {"global_admin": True}})
    before = db.users.find_one({"_id": target})
    response = _client_for_user(app, actor).post(f"/admin/user/save_user/{target}", data=_form(before))
    assert response.status_code == 403
    assert db.users.find_one({"_id": target}) == before


def test_organization_admin_role_does_not_grant_global_user_management(app, db, seeded_data):
    actor = _create_organization_admin(db, seeded_data["org_id"], ["EDIT_ORGANIZATION"])
    target = seeded_data["user_id"]
    client = _client_for_user(app, actor)
    assert client.get("/admin/user/").status_code == 403
    assert client.get(f"/admin/user/api/check_clearance/{target}").status_code == 403
    assert client.post(f"/admin/user/save_user/{target}", data=_form(db.users.find_one({"_id": target}))).status_code == 403
    assert client.post("/admin/user/api/force_password_change/", json={"user_id": str(target)}).status_code == 403


@pytest.mark.parametrize("target_kind", ["self", "peer", "higher"])
def test_force_password_change_respects_target_hierarchy(admin_client, db, seeded_data, target_kind):
    target = seeded_data["admin_id"] if target_kind == "self" else seeded_data["user_id"]
    if target_kind != "self":
        db.users.update_one({"_id": target}, {"$set": {"role": "admin" if target_kind == "peer" else "god"}})
    before = db.users.find_one({"_id": target})
    response = admin_client.post("/admin/user/api/force_password_change/", json={"user_id": str(target)})
    assert response.status_code == 403
    assert db.users.find_one({"_id": target}) == before


def test_ordinary_target_profile_edit_still_works(admin_client, db, seeded_data):
    target = seeded_data["user_id"]
    data = _form(db.users.find_one({"_id": target}))
    data["displayname"] = "Updated Display"
    response = admin_client.post(f"/admin/user/save_user/{target}", data=data)
    assert response.status_code == 302
    assert db.users.find_one({"_id": target})["displayname"] == "Updated Display"


def test_admin_can_edit_own_basic_profile_without_changing_authority(admin_client, db, seeded_data):
    target = seeded_data["admin_id"]
    # Use a valid public identity so reserved-name validation does not mask
    # the target/authority behavior this regression exercises.
    db.users.update_one({"_id": target}, {"$set": {
        "username": "siteoperator", "username_canonical": "siteoperator",
    }})
    before = db.users.find_one({"_id": target})
    assert admin_client.get(f"/admin/user/edit_user/{target}").status_code == 200
    data = _form(before, role=before["role"])
    data["permissions[global][]"] = before["global_permissions"]
    data["displayname"] = "Own Display Updated"
    assert admin_client.post(f"/admin/user/save_user/{target}", data=data).status_code == 302
    after = db.users.find_one({"_id": target})
    assert after["displayname"] == "Own Display Updated"
    assert after["role"] == before["role"]
    assert set(after["global_permissions"]) == set(before["global_permissions"])


def test_hard_coded_identity_has_no_hierarchy_exception():
    actor = SimpleNamespace(_id=ObjectId("66c25768dad432ad39ce38d5"), role="user")
    target = SimpleNamespace(_id=ObjectId(), role="god")
    assert not compare_user_levels(actor, target)
    assert target.role == "god"


def test_admin_user_audit_excludes_credentials_and_request_payload(admin_client, db, seeded_data):
    marker = "synthetic-private-payload"
    response = admin_client.post("/admin/user/api/force_password_change/", query_string={'secret': marker}, json={
        "user_id": str(seeded_data["user_id"]), "password": marker,
    }, headers={"Authorization": marker})
    assert response.status_code == 200
    logs = list(db.admin_logs.find({"event": "admin_user_request"}))
    assert logs
    assert marker not in repr(logs)
    assert logs[0]['request']['args'] == {'secret': []}
    assert "password_hash" not in repr(logs)
    action = db.admin_logs.find_one({"event": "user_password_reset_required"})
    assert action["entity_id"] == str(seeded_data["user_id"])
    assert marker not in repr(action)
    assert action['request']['args'] == {'secret': []}
    super_logs = list(db.super_audit_logs.find({'event': {'$in': [
        'admin:admin_user_request', 'admin:user_password_reset_required',
    ]}}))
    assert {event['event'] for event in super_logs} == {
        'admin:admin_user_request', 'admin:user_password_reset_required',
    }
    assert marker not in repr(super_logs)
    assert all(event['request']['args'] == {'secret': []} for event in super_logs)


@pytest.mark.parametrize("role,expected_status", [("god", 302), ("global_admin", 403)])
def test_create_user_cannot_bypass_superuser_promotion_process(admin_client, db, role, expected_status):
    response = admin_client.post("/admin/user/create_user", data={
        "username": "forged-root", "email": "forged-root@example.test", "role": role,
    })
    assert response.status_code == expected_status
    assert db.users.find_one({"username": "forged-root"}) is None
