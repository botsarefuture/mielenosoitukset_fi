"""The Flask/Vite boundary must resolve complete builds under the static prefix."""

import json

from flask import Flask
import pytest

from mielenosoitukset_fi.utils.frontend import frontend_assets


def test_frontend_manifest_resolves_dependency_css_once_and_reloads_build(tmp_path):
    build = tmp_path / "frontend"
    build.mkdir()
    for filename in ("shared.css", "page.css", "page.js", "rebuilt.js"):
        (build / filename).write_text("", encoding="utf-8")
    manifest = {
        "shared": {"file": "page.js", "css": ["shared.css"]},
        "entry": {"file": "page.js", "imports": ["shared"], "css": ["shared.css", "page.css"]},
    }
    manifest_path = build / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    app = Flask(__name__, static_folder=str(tmp_path), static_url_path="/assets")
    with app.test_request_context():
        assert frontend_assets("entry") == {
            "script": "/assets/frontend/page.js",
            "styles": ["/assets/frontend/shared.css", "/assets/frontend/page.css"],
        }
        manifest["entry"]["file"] = "rebuilt.js"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        assert frontend_assets("entry")["script"] == "/assets/frontend/rebuilt.js"


@pytest.mark.parametrize("filename", ["missing.js", "../outside.js", "/outside.js"])
def test_frontend_manifest_rejects_incomplete_or_escaping_build(tmp_path, filename):
    build = tmp_path / "frontend"
    build.mkdir()
    (build / "manifest.json").write_text(json.dumps({"entry": {"file": filename}}))
    app = Flask(__name__, static_folder=str(tmp_path))
    with app.test_request_context(), pytest.raises(ValueError):
        frontend_assets("entry")
