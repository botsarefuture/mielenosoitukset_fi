import ast
import unittest
from pathlib import Path
import re

import yaml

from tests._surface_inventory import APP_ROOT, collect_api_route_entries


API_SPEC_PATH = Path("mielenosoitukset_fi/api/api.yaml")


def _admin_scoped_api_routes() -> set:
    """
    Return the set of api_bp routes that require admin scopes/perms.

    These routes are deliberately excluded from the public OpenAPI spec.
    """
    path = APP_ROOT / "api" / "routes.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    routes = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        route = None
        admin = False
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            func_name = (
                decorator.func.attr
                if isinstance(decorator.func, ast.Attribute)
                else decorator.func.id
                if isinstance(decorator.func, ast.Name)
                else None
            )
            if func_name == "route" and decorator.args:
                if isinstance(decorator.args[0], ast.Constant):
                    route = decorator.args[0].value
            if func_name in ("token_required", "_token_or_session_required"):
                for keyword in decorator.keywords:
                    if keyword.arg == "required_scopes":
                        if isinstance(keyword.value, (ast.List, ast.Tuple)):
                            for item in keyword.value.elts:
                                if (
                                    isinstance(item, ast.Constant)
                                    and item.value == "admin"
                                ):
                                    admin = True
                    if keyword.arg == "required_perms":
                        admin = True
        if route is not None and admin:
            routes[route] = True
    return set(routes)


def _normalize_route(route: str) -> str:
    return re.sub(r"<(?:[^:>]+:)?([^>]+)>", r"{\1}", route)


def _full_path(entry) -> str:
    prefix = entry.get("prefix") or ""
    route = _normalize_route(entry["route"] or "")
    return prefix.rstrip("/") + route


class ApiContractTests(unittest.TestCase):
    def test_openapi_paths_and_methods_match_api_routes(self):
        admin_routes = _admin_scoped_api_routes()
        implemented_external = {
            _full_path(entry): {method.lower() for method in entry["methods"]}
            for entry in collect_api_route_entries()
            if (entry["route"] or "") not in admin_routes
        }
        spec = yaml.safe_load(API_SPEC_PATH.read_text(encoding="utf-8"))
        documented = {
            path: {method.lower() for method in methods.keys()}
            for path, methods in spec["paths"].items()
        }

        for path, methods in implemented_external.items():
            with self.subTest(path=path):
                self.assertIn(
                    path,
                    documented,
                    msg="External api_bp route is missing from the OpenAPI spec",
                )
                self.assertEqual(methods, documented[path])

        for route in admin_routes:
            full_path = _full_path(
                {
                    "prefix": "/api/",
                    "route": route,
                }
            )
            with self.subTest(admin_path=full_path):
                self.assertNotIn(
                    full_path,
                    documented,
                    msg="Admin-scoped api_bp route must not appear in the public spec",
                )

    def test_openapi_documents_external_non_bp_endpoints(self):
        """The spec also covers /api/v1 and /users/auth endpoints."""
        spec = yaml.safe_load(API_SPEC_PATH.read_text(encoding="utf-8"))
        paths = set(spec["paths"])
        self.assertIn("/api/v1/demonstrations", paths)
        self.assertIn("/api/v1/check_demo_conflict", paths)
        self.assertIn("/api/v1/search_organizations", paths)
        self.assertIn("/users/auth/api_token", paths)
        self.assertIn("/users/auth/api_tokens/list", paths)
        self.assertIn("/users/auth/api_tokens/revoke", paths)
        self.assertIn("/users/auth/api_tokens/status", paths)
        self.assertIn("/users/auth/api_tokens/request_access", paths)

    @staticmethod
    def _normalize_route(route: str) -> str:
        return re.sub(r"<(?:[^:>]+:)?([^>]+)>", r"{\1}", route)


if __name__ == "__main__":
    unittest.main()