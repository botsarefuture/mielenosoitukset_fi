"""Organization admin mutations reject invalid data before database writes."""

import pytest
from bson import ObjectId
from tests.conftest import _client_for_user
from tests.test_city_scoped_admin import _create_organization_admin

ENDPOINTS = [
    "delete_membership", "force_accept_invite", "cancel_invite",
    "set_invite_role", "change_access_level",
]


@pytest.mark.parametrize("endpoint", ENDPOINTS)
@pytest.mark.parametrize("payload", [[], "wrong shape", {"organization_id": "bad-id", "membership_id": [], "user_id": {}, "email": []}])
def test_org_action_rejects_malformed_json_or_identifiers(admin_client, endpoint, payload):
    response = admin_client.post(f"/admin/organization/api/{endpoint}/", json=payload)
    assert response.status_code == 400
    assert response.get_json()["status"] == "error"


@pytest.mark.parametrize("email", ["not-an-email", [], "alice@example.test\nBcc:other@example.test"])
@pytest.mark.parametrize("endpoint", ["force_accept_invite", "cancel_invite", "set_invite_role"])
def test_invitation_actions_reject_invalid_addresses(admin_client, seeded_data, endpoint, email):
    response = admin_client.post(f"/admin/organization/api/{endpoint}/", json={
        "organization_id": str(seeded_data["org_id"]), "email": email, "role": "member",
    })
    assert response.status_code == 400


def test_invite_role_normalizes_input_and_matches_legacy_address(admin_client, db, seeded_data):
    org_id = seeded_data["org_id"]
    db.organizations.update_one({"_id": org_id}, {"$set": {"invitations": ["ALICE@example.test"]}})
    response = admin_client.post("/admin/organization/api/set_invite_role/", json={
        "organization_id": str(org_id), "email": " Alice@Example.Test ", "role": "member",
    })
    assert response.status_code == 200
    assert db.organizations.find_one({"_id": org_id})["invitations"] == [
        {"email": "alice@example.test", "role": "member"},
    ]
    response = admin_client.post("/admin/organization/api/cancel_invite/", json={
        "organization_id": str(org_id), "email": " ALICE@example.test ",
    })
    assert response.status_code == 200
    assert db.organizations.find_one({"_id": org_id})["invitations"] == []


def test_organization_editor_cannot_mutate_another_org_invite(app, db, seeded_data):
    actor = _create_organization_admin(db, seeded_data["org_id"], [
        "EDIT_ORGANIZATION", "INVITE_TO_ORGANIZATION",
    ])
    foreign_id = ObjectId()
    db.organizations.insert_one({"_id": foreign_id, "name": "Foreign", "verified": True, "invitations": []})
    client = _client_for_user(app, actor)
    response = client.post("/admin/organization/api/set_invite_role/", json={
        "organization_id": str(foreign_id), "email": "outsider@example.test", "role": "owner",
    })
    assert response.status_code == 403
    assert db.organizations.find_one({"_id": foreign_id})["invitations"] == []


def test_invite_form_rejects_invalid_object_identifier(admin_client):
    response = admin_client.post("/admin/organization/invite", data={
        "organization_id": "bad-id", "invitee_email": "alice@example.test",
    })
    assert response.status_code == 400


@pytest.mark.parametrize("target_kind", ["own", "foreign", "orphan", "malformed_org"])
def test_membership_delete_requires_resolved_target_organization(app, db, seeded_data, target_kind):
    org_id = seeded_data["org_id"]
    actor = _create_organization_admin(db, org_id, ["EDIT_ORGANIZATION"])
    target_org = org_id
    if target_kind == "foreign":
        target_org = ObjectId()
        db.organizations.insert_one({"_id": target_org, "name": "Foreign", "verified": True})
    elif target_kind == "orphan":
        target_org = ObjectId()
    elif target_kind == "malformed_org":
        target_org = "invalid"
    target = ObjectId()
    db.memberships.insert_one({
        "_id": target, "user_id": seeded_data["user_id"],
        "organization_id": target_org, "role": "member", "permissions": [],
    })
    client = _client_for_user(app, actor)
    response = client.post("/admin/organization/api/delete_membership/", json={
        "membership_id": str(target),
    })
    assert response.status_code == {"own": 200, "foreign": 403, "orphan": 404, "malformed_org": 404}[target_kind]
    assert (db.memberships.find_one({"_id": target}) is None) == (target_kind == "own")
