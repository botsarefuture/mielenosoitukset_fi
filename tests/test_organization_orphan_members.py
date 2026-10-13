"""Organization reads must tolerate legacy references to missing users."""

from bson import ObjectId
import pytest

from mielenosoitukset_fi.utils.classes.Organization import Organization
from mielenosoitukset_fi.users.models import User


def _orphan(db, org_id, user_id=None):
    membership = {
        "_id": ObjectId(), "user_id": user_id if user_id is not None else ObjectId(),
        "organization_id": org_id, "role": "owner", "permissions": ["EDIT_ORGANIZATION"],
    }
    db.memberships.insert_one(membership)
    return membership


@pytest.mark.parametrize("identifier_kind", ["object", "string"])
@pytest.mark.parametrize("client_fixture", ["client", "user_client"])
def test_organization_detail_renders_with_missing_member(db, seeded_data, request, identifier_kind, client_fixture):
    org_id = seeded_data["org_id"]
    missing = ObjectId()
    _orphan(db, org_id, str(missing) if identifier_kind == "string" else missing)
    memberships_before = list(db.memberships.find({"organization_id": org_id}).sort("_id", 1))
    client = request.getfixturevalue(client_fixture)
    response = client.get(f"/organization/{org_id}")
    assert response.status_code == 200
    assert "Test Organization" in response.get_data(as_text=True)
    assert db.users.find_one({"_id": missing}) is None
    assert list(db.memberships.find({"organization_id": org_id}).sort("_id", 1)) == memberships_before


def test_organization_preserves_valid_members_and_permissions(db, seeded_data):
    org_id = seeded_data["org_id"]
    missing = _orphan(db, org_id)["user_id"]
    original_users = {doc["_id"]: doc for doc in db.users.find()}
    org = Organization.from_dict(db.organizations.find_one({"_id": org_id}))
    assert {member._id for member in org.members} == {seeded_data["admin_id"], seeded_data["user_id"]}
    members = {member._id: member for member in org.members}
    assert members[seeded_data["admin_id"]].role == "owner"
    assert members[seeded_data["user_id"]].role == "admin"
    assert "EDIT_ORGANIZATION" in members[seeded_data["user_id"]].permissions
    assert "CREATE_DEMO" in members[seeded_data["user_id"]].permissions
    assert org.is_member(user_id=seeded_data["user_id"])
    assert not org.is_member(user_id=missing)
    assert org.get_member(missing) is None
    assert {doc["_id"]: doc for doc in db.users.find()} == original_users
    org.init_members()
    assert len(org.members) == 2


def test_organization_with_only_orphan_members_renders_empty_members(client, db, seeded_data):
    document = db.organizations.find_one({"_id": seeded_data["org_id"]})
    document.update({"_id": ObjectId(), "name": "Orphan-only organization"})
    db.organizations.insert_one(document)
    _orphan(db, document["_id"])
    _orphan(db, document["_id"])
    org = Organization.from_dict(dict(document))
    assert org.members == []
    response = client.get(f"/organization/{document['_id']}")
    assert response.status_code == 200
    assert "Orphan-only organization" in response.get_data(as_text=True)
    assert db.memberships.count_documents({"organization_id": document["_id"]}) == 2


def test_organization_does_not_suppress_other_user_loading_errors(db, seeded_data, monkeypatch):
    def invalid_user(_cls, _user_id):
        raise ValueError("Invalid persisted user schema")
    monkeypatch.setattr(User, "from_OID", classmethod(invalid_user))
    with pytest.raises(ValueError, match="Invalid persisted user schema"):
        Organization.from_dict(db.organizations.find_one({"_id": seeded_data["org_id"]}))
