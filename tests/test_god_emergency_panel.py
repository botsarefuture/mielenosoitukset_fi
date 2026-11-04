import base64
import importlib.util
import io
import json
from pathlib import Path
import re
from urllib.parse import urlencode

import pytest

from mielenosoitukset_fi.utils.emergency_signatures import PANEL_DOMAIN, verify

PANEL = Path(__file__).resolve().parents[1] / "deploy" / "panel" / "moso_emergency_panel.py"


def load_panel():
    spec = importlib.util.spec_from_file_location("moso_emergency_panel", PANEL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeHandler:
    def __init__(self, path, command="GET", body=b"", headers=None):
        self.path = path
        self.command = command
        self.headers = headers or {}
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.status = None
        self.response_headers = {}

    def send_response(self, status):
        self.status = status

    def send_header(self, name, value):
        self.response_headers[name] = value

    def end_headers(self):
        pass

    def send_error(self, status):
        self.status = status

    @property
    def location(self):
        return self.response_headers.get("Location", "")

    @property
    def text(self):
        return self.wfile.getvalue().decode("utf-8")


@pytest.fixture
def panel(tmp_path, monkeypatch):
    module = load_panel()
    private = tmp_path / "panel"
    registered = module.initialize(private)
    config = {"enabled": True, "origins": ["http://panel.lan"],
              "private_key": str(private / "private.pem"), "candidate_id": "",
              "admin_base": "https://mielenosoitukset.fi"}
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    monkeypatch.setattr(module, "CONFIG", path)
    return module, registered, path


def save(path, config):
    path.write_text(json.dumps(config))


def page_token(handler):
    return re.search(r'name="csrf" value="([^"]+)"', handler.text).group(1)


def post(module, csrf, origin="http://panel.lan", cookie=None, **fields):
    body = urlencode({"csrf": csrf, "candidate_id": "a" * 24,
                      "reason": "Emergency appointment for regression testing", **fields}).encode()
    headers = {"Content-Length": str(len(body)), "Origin": origin,
               "Cookie": "moso_emergency_csrf=" + (csrf if cookie is None else cookie)}
    handler = FakeHandler("/moso-emergency", "POST", body, headers)
    module.handle(handler, authed=True)
    return handler


def test_lan_page_requires_the_panel_passphrase(panel):
    module, _, _ = panel
    handler = FakeHandler("/moso-emergency")
    module.handle(handler, authed=False)
    assert handler.status == 303 and handler.location == "/logins"
    assert handler.text == ""


def test_lan_page_renders_only_for_authenticated_panel_sessions(panel):
    module, _, _ = panel
    handler = FakeHandler("/moso-emergency")
    module.handle(handler, authed=True)
    assert handler.status == 200
    assert "God emergency appointment" in handler.text
    assert "two distinct board members" in handler.text
    assert handler.response_headers["Cache-Control"] == "no-store"
    assert page_token(handler)


def test_panel_ticket_is_signed_for_the_administration_origin(panel):
    module, registered, _ = panel
    handler = post(module, "csrf-token")
    assert handler.status == 303
    assert handler.location.startswith("https://mielenosoitukset.fi/admin/governance/clearances#emergency=")
    encoded = handler.location.split("#emergency=", 1)[1]
    ticket = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    message = verify(ticket, {registered["key_id"]: registered["public_key"]}, PANEL_DOMAIN)
    assert message["candidate_id"] == "a" * 24
    assert message["reason"] == "Emergency appointment for regression testing"
    assert 0 < message["expires_at"] - message["issued_at"] <= 300
    assert 32 <= len(message["launch_id"]) <= 100
    assert ticket["key_id"] == registered["key_id"]


def test_panel_rejects_foreign_origins_bad_csrf_and_invalid_fields(panel):
    module, _, _ = panel
    foreign = post(module, "csrf-token", origin="http://evil.example")
    assert foreign.status == 200 and "could not be opened" in foreign.text
    bad_csrf = post(module, "csrf-token", cookie="different-token")
    assert bad_csrf.status == 200 and "could not be opened" in bad_csrf.text
    short = post(module, "csrf-token", candidate_id="../../etc", reason="x")
    assert short.status == 200 and "could not be opened" in short.text


def test_panel_refuses_to_sign_until_activation(panel):
    module, _, path = panel
    save(path, {**json.loads(path.read_text()), "enabled": False})
    handler = post(module, "csrf-token")
    assert handler.status == 200 and "could not be opened" in handler.text
    assert "Approval is disabled" in handler.text


def test_panel_ignores_other_paths(panel):
    module, _, _ = panel
    handler = FakeHandler("/other")
    module.handle(handler, authed=True)
    assert handler.status == 404
