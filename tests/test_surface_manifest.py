import json
import unittest
from pathlib import Path

from tests._surface_inventory import (
    collect_background_job_surface,
    collect_route_surfaces,
    collect_socketio_surface,
)


MANIFEST_PATH = Path(__file__).with_name("surface_manifest.json")


class SurfaceManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_route_surface_manifest_matches_source(self):
        expected = self.manifest["routes"]
        actual = collect_route_surfaces()

        self.assertEqual(set(actual), set(expected))
        for path, expected_meta in expected.items():
            with self.subTest(path=path):
                self.assertGreater(len(expected_meta.get("coverage", [])), 0)
                self.assertEqual(actual[path]["count"], expected_meta["count"])
                self.assertEqual(actual[path]["sha256"], expected_meta["sha256"])

    def test_background_job_surface_manifest_matches_source(self):
        expected = self.manifest["background_jobs"]
        actual = collect_background_job_surface()

        self.assertGreater(len(expected.get("coverage", [])), 0)
        self.assertEqual(actual["count"], expected["count"])
        self.assertEqual(actual["sha256"], expected["sha256"])

    def test_socketio_surface_manifest_matches_source(self):
        expected = self.manifest["socketio"]
        actual = collect_socketio_surface()

        self.assertGreater(len(expected.get("coverage", [])), 0)
        self.assertEqual(actual["count"], expected["count"])
        self.assertEqual(actual["sha256"], expected["sha256"])


if __name__ == "__main__":
    unittest.main()
