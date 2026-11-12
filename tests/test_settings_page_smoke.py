"""Quick smoke: settings + login templates still render after frontend edits."""

import re

from tests.conftest import _client_for_user, _cleanup_app_resources


def test_settings_page_renders_after_stepup_rewrite(app_factory, db, seeded_data):
    app = app_factory(WEBAUTHN_ORIGIN="http://localhost", WEBAUTHN_RP_ID="localhost")
    try:
        client = _client_for_user(app, seeded_data["user_id"])
        r = client.get("/users/auth/settings")
        assert r.status_code == 200, r.get_data(as_text=True)[:500]
        html = r.get_data(as_text=True)

        assert "stepUpModal" in html
        assert "add-passkey-btn" in html
        assert "window.fetchWithStepUp = fetchWithStepUp" in html
        # the block must not reference bootstrap at parse-time
        block = re.findall(r"<script(?![^>]*src=)[^>]*>(.*?)</script>", html, flags=re.S)
        tail = "\n".join(block[-1:])
        assert "new bootstrap.Modal" not in tail.split("function getStepUpModal")[0]
    finally:
        _cleanup_app_resources(app)