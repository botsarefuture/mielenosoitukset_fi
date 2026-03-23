import unittest
from unittest.mock import patch

from flask import Flask
from werkzeug.exceptions import Forbidden, Gone

from mielenosoitukset_fi.utils import wrappers


class FakeCurrentUser:
    def __init__(
        self,
        *,
        is_authenticated=True,
        global_admin=False,
        global_permissions=None,
        has_permission=False,
        username="tester",
    ):
        self.is_authenticated = is_authenticated
        self.global_admin = global_admin
        self.global_permissions = global_permissions or []
        self._has_permission = has_permission
        self.username = username
        self.id = "user-1"

    def has_permission(self, permission_name, organization_id=None, strict=False):
        return self._has_permission


class WrapperDecoratorTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = "test-secret"

        @wrappers.permission_required("EDIT_DEMO")
        def protected_view():
            return "ok"

        @wrappers.permission_required(
            "EDIT_DEMO",
            _id="demo-id",
            _type="DEMONSTRATION",
        )
        def protected_demo_view():
            return "demo-ok"

        @wrappers.depracated_endpoint
        def deprecated_view():
            return "should-not-run"

        self.protected_view = protected_view
        self.protected_demo_view = protected_demo_view
        self.deprecated_view = deprecated_view

    def test_permission_required_redirects_unauthenticated_users(self):
        user = FakeCurrentUser(is_authenticated=False)

        with self.app.test_request_context("/protected"):
            with patch.object(wrappers, "current_user", user), patch.object(
                wrappers,
                "url_for",
                return_value="/users/auth/login",
            ), patch.object(wrappers, "flash_message") as flash_message:
                response = self.protected_view()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/users/auth/login")
        flash_message.assert_called_once()

    def test_permission_required_allows_users_with_permission(self):
        user = FakeCurrentUser(has_permission=True)

        with self.app.test_request_context("/protected"):
            with patch.object(wrappers, "current_user", user):
                response = self.protected_view()

        self.assertEqual(response, "ok")

    def test_permission_required_aborts_when_demo_permission_is_missing(self):
        user = FakeCurrentUser()

        with self.app.test_request_context("/demo-protected"):
            with patch.object(wrappers, "current_user", user), patch.object(
                wrappers,
                "has_demo_permission",
                return_value=False,
            ), patch.object(wrappers, "flash_message") as flash_message:
                with self.assertRaises(Forbidden):
                    self.protected_demo_view()

        flash_message.assert_called_once()

    def test_permission_required_allows_demonstration_access_when_granted(self):
        user = FakeCurrentUser()

        with self.app.test_request_context("/demo-protected"):
            with patch.object(wrappers, "current_user", user), patch.object(
                wrappers,
                "has_demo_permission",
                return_value=True,
            ):
                response = self.protected_demo_view()

        self.assertEqual(response, "demo-ok")

    def test_deprecated_endpoint_aborts_with_gone(self):
        with self.app.test_request_context("/deprecated"):
            with patch.object(wrappers, "flash_message") as flash_message:
                with self.assertRaises(Gone):
                    self.deprecated_view()

        flash_message.assert_called_once_with(
            "This endpoint is deprecated and no longer available."
        )


if __name__ == "__main__":
    unittest.main()
