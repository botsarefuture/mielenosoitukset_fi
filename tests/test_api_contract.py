import unittest
from pathlib import Path
import re

import yaml

from tests._surface_inventory import collect_api_route_entries


API_SPEC_PATH = Path("mielenosoitukset_fi/api/api.yaml")


class ApiContractTests(unittest.TestCase):
    def test_openapi_paths_and_methods_match_api_routes(self):
        implemented = {
            self._normalize_route(entry["route"]): {
                method.lower() for method in entry["methods"]
            }
            for entry in collect_api_route_entries()
        }
        spec = yaml.safe_load(API_SPEC_PATH.read_text(encoding="utf-8"))
        documented = {
            path: {method.lower() for method in methods.keys()}
            for path, methods in spec["paths"].items()
        }

        self.assertEqual(set(implemented), set(documented))
        for path, methods in implemented.items():
            with self.subTest(path=path):
                self.assertEqual(methods, documented[path])

    @staticmethod
    def _normalize_route(route: str) -> str:
        return re.sub(r"<(?:[^:>]+:)?([^>]+)>", r"{\1}", route)


if __name__ == "__main__":
    unittest.main()
