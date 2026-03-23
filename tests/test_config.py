import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config as config_module
from mielenosoitukset_fi.database_manager import DatabaseManager


class ConfigReloadTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("CONFIG_YAML_PATH", None)
        config_module.Config.reload()
        DatabaseManager.reset_instance()

    def test_reload_reads_config_from_env_selected_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "MONGO_URI: mongodb://example.test:27017",
                        "MONGO_DBNAME: integration_suite",
                        "PORT: 9001",
                        "DEFAULT_TIMEZONE: UTC",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"CONFIG_YAML_PATH": str(config_path)}):
                config_module.Config.reload()

            self.assertEqual(
                config_module.Config.MONGO_URI,
                "mongodb://example.test:27017",
            )
            self.assertEqual(config_module.Config.MONGO_DBNAME, "integration_suite")
            self.assertEqual(config_module.Config.PORT, 9001)
            self.assertEqual(config_module.Config.DEFAULT_TIMEZONE, "UTC")

    def test_database_manager_reset_clears_singleton(self):
        class FakeManager:
            def __init__(self):
                self.closed = False

            def close_connection(self):
                self.closed = True

        original = DatabaseManager._instance
        fake = FakeManager()
        DatabaseManager._instance = fake
        try:
            DatabaseManager.reset_instance()
            self.assertTrue(fake.closed)
            self.assertIsNone(DatabaseManager._instance)
        finally:
            DatabaseManager._instance = original


if __name__ == "__main__":
    unittest.main()
