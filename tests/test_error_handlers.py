import unittest
from unittest.mock import call, patch

from flask import Flask, abort

from mielenosoitukset_fi.error_handlers import register_error_handlers


class ErrorHandlerTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

        @self.app.route("/bad-request")
        def bad_request():
            abort(400)

        @self.app.route("/unauthorized")
        def unauthorized():
            abort(401)

        @self.app.route("/forbidden")
        def forbidden():
            abort(403)

        @self.app.route("/gone")
        def gone():
            abort(410)

        @self.app.route("/too-many")
        def too_many():
            abort(429)

        @self.app.route("/error")
        def error():
            raise RuntimeError("boom")

        register_error_handlers(self.app)
        self.client = self.app.test_client()

    def test_handlers_render_expected_templates(self):
        checks = [
            ("/bad-request", "errors/400.html", 400),
            ("/unauthorized", "errors/401.html", 401),
            ("/forbidden", "errors/403.html", 403),
            ("/missing", "errors/404.html", 404),
            ("/gone", "errors/410.html", 410),
            ("/too-many", "errors/429.html", 429),
            ("/error", "errors/500.html", 500),
        ]

        with patch(
            "mielenosoitukset_fi.error_handlers.render_template",
            return_value="handled",
        ) as render_template:
            for path, template_name, status_code in checks:
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, status_code)
                    self.assertEqual(response.get_data(as_text=True), "handled")

        self.assertEqual(
            render_template.call_args_list,
            [call(template_name) for _, template_name, _ in checks],
        )


if __name__ == "__main__":
    unittest.main()
