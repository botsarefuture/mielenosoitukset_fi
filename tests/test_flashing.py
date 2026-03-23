import unittest

from flask import Flask, g, get_flashed_messages
from flask_babel import Babel

from mielenosoitukset_fi.utils.flashing import flash_message


class FlashMessageTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = "test-secret"
        Babel(self.app)

    def test_flash_message_marks_request_and_maps_success_category(self):
        with self.app.test_request_context("/"):
            flash_message("Saved", "approved")

            self.assertTrue(g._has_flash_messages)
            self.assertEqual(
                get_flashed_messages(with_categories=True),
                [("success", "Saved")],
            )

    def test_flash_message_falls_back_to_default_category(self):
        with self.app.test_request_context("/"):
            flash_message("Heads up", "not-a-real-category")

            self.assertTrue(g._has_flash_messages)
            self.assertEqual(
                get_flashed_messages(with_categories=True),
                [("default", "Heads up")],
            )


if __name__ == "__main__":
    unittest.main()
