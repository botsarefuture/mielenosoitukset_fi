import unittest
from unittest.mock import Mock, patch

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
        for global_admin in (False, True):
            with self.subTest(global_admin=global_admin):
                user = FakeCurrentUser(is_authenticated=False, global_admin=global_admin)
                with self.app.test_request_context("/protected"):
                    with patch.object(wrappers, "current_user", user), patch.object(
                        wrappers,
                        "url_for",
                        return_value="/users/auth/login",
                    ) as login_url, patch.object(wrappers, "flash_message") as flash_message:
                        response = self.protected_view()

                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.location, "/users/auth/login")
                login_url.assert_called_once_with("users.auth.login")
                flash_message.assert_called_once()

    def test_permission_required_allows_users_with_permission(self):
        user = FakeCurrentUser(has_permission=True)

        with self.app.test_request_context("/protected"):
            with patch.object(wrappers, "current_user", user), patch.object(
                user, "has_permission", return_value=True
            ) as permission_check:
                response = self.protected_view()

        self.assertEqual(response, "ok")
        permission_check.assert_called_once_with("EDIT_DEMO", None)

    def test_permission_required_denies_users_without_permission(self):
        user = FakeCurrentUser()
        handler = Mock(return_value="should-not-run")
        protected = wrappers.permission_required("EDIT_DEMO")(handler)

        with self.app.test_request_context("/protected"):
            with patch.object(wrappers, "current_user", user), patch.object(
                wrappers, "flash_message"
            ) as flash_message:
                with self.assertRaises(Forbidden):
                    protected()

        handler.assert_not_called()
        flash_message.assert_called_once()

    def test_permission_required_aborts_when_demo_permission_is_missing(self):
        user = FakeCurrentUser()

        with self.app.test_request_context("/demo-protected"):
            with patch.object(wrappers, "current_user", user), patch.object(
                wrappers,
                "has_demo_permission",
                return_value=False,
            ) as permission_check, patch.object(wrappers, "flash_message") as flash_message:
                with self.assertRaises(Forbidden):
                    self.protected_demo_view()

        flash_message.assert_called_once()
        permission_check.assert_called_once_with(user, "demo-id", "EDIT_DEMO")

    def test_permission_required_allows_demonstration_access_when_granted(self):
        user = FakeCurrentUser()
        handler = Mock(return_value="demo-ok")
        dynamic_view = wrappers.permission_required("EDIT_DEMO", _type="DEMONSTRATION")(handler)
        for view, kwargs, demo_id in [
            (self.protected_demo_view, {}, "demo-id"),
            (dynamic_view, {"demo_id": "route-demo"}, "route-demo"),
        ]:
            with self.subTest(demo_id=demo_id):
                with self.app.test_request_context("/demo-protected"):
                    with patch.object(wrappers, "current_user", user), patch.object(
                        wrappers,
                        "has_demo_permission",
                        return_value=True,
                    ) as permission_check:
                        response = view(**kwargs)

                self.assertEqual(response, "demo-ok")
                permission_check.assert_called_once_with(user, demo_id, "EDIT_DEMO")
        handler.assert_called_once_with(demo_id="route-demo")

    def test_deprecated_endpoint_aborts_with_gone(self):
        with self.app.test_request_context("/deprecated"):
            with patch.object(wrappers, "flash_message") as flash_message:
                with self.assertRaises(Gone):
                    self.deprecated_view()

        flash_message.assert_called_once()


if __name__ == "__main__":
    unittest.main()
