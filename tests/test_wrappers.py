import unittest
from unittest.mock import patch

from bson import ObjectId

from mielenosoitukset_fi.utils import wrappers


class FakeCollection:
    def __init__(self, docs):
        self.docs = docs

    def find_one(self, query):
        return self.docs.get(query.get("_id"))


class FakeMongo:
    def __init__(self, docs):
        self.demonstrations = FakeCollection(docs)


class FakeUser:
    def __init__(self, *, is_authenticated=True, global_admin=False, permissions=None):
        self.is_authenticated = is_authenticated
        self.global_admin = global_admin
        self._id = ObjectId()
        self.id = str(self._id)
        self.permissions = permissions or {}

    def has_permission(self, perm, organization_id=None, strict=False):
        key = (perm, str(organization_id) if organization_id else None)
        return self.permissions.get(key, False)


class HasDemoPermissionTests(unittest.TestCase):
    def test_denies_for_unauthenticated_user(self):
        user = FakeUser(is_authenticated=False)
        self.assertFalse(
            wrappers.has_demo_permission(user, ObjectId(), "EDIT_DEMO"),
            "Unauthenticated users should not be authorized.",
        )

    def test_denies_for_invalid_demo_id(self):
        user = FakeUser()
        self.assertFalse(
            wrappers.has_demo_permission(user, "not-a-valid-id", "EDIT_DEMO"),
            "Invalid IDs should be rejected early.",
        )

    def test_denies_when_demo_missing(self):
        user = FakeUser()
        with patch(
            "mielenosoitukset_fi.utils.wrappers._get_mongo",
            return_value=FakeMongo({}),
        ):
            self.assertFalse(
                wrappers.has_demo_permission(user, ObjectId(), "EDIT_DEMO"),
                "Missing demonstrations should not grant access.",
            )

    def test_allows_user_listed_as_editor(self):
        user = FakeUser()
        demo_id = ObjectId()
        demo_doc = {demo_id: {"_id": demo_id, "editors": [user.id]}}
        with patch(
            "mielenosoitukset_fi.utils.wrappers._get_mongo",
            return_value=FakeMongo(demo_doc),
        ):
            self.assertTrue(
                wrappers.has_demo_permission(user, demo_id, "EDIT_DEMO"),
                "Editors should be authorized for demo actions.",
            )

    def test_allows_permission_via_organizer_membership(self):
        org_id = ObjectId()
        user = FakeUser(permissions={("EDIT_DEMO", str(org_id)): True})
        demo_id = ObjectId()
        demo_doc = {
            demo_id: {
                "_id": demo_id,
                "organizers": [{"organization_id": org_id}],
            }
        }
        with patch(
            "mielenosoitukset_fi.utils.wrappers._get_mongo",
            return_value=FakeMongo(demo_doc),
        ):
            self.assertTrue(
                wrappers.has_demo_permission(user, demo_id, "EDIT_DEMO"),
                "Users with organizer permissions should be authorized.",
            )

    def test_denies_without_matching_permissions(self):
        org_id = ObjectId()
        user = FakeUser()
        demo_id = ObjectId()
        demo_doc = {
            demo_id: {
                "_id": demo_id,
                "organizers": [{"organization_id": org_id}],
            }
        }
        with patch(
            "mielenosoitukset_fi.utils.wrappers._get_mongo",
            return_value=FakeMongo(demo_doc),
        ):
            self.assertFalse(
                wrappers.has_demo_permission(user, demo_id, "EDIT_DEMO"),
                "Users without relevant permissions should be denied.",
            )


if __name__ == "__main__":
    unittest.main()
