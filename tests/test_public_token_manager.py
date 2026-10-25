"""Focused contracts for the public API-token manager."""

from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import urlsplit

import pytest

from mielenosoitukset_fi.api.exceptions import ApiException
from mielenosoitukset_fi.utils.tokens import check_token, create_token


ROOT = Path(__file__).resolve().parents[1]
TOKEN_TEMPLATE = ROOT / "mielenosoitukset_fi/templates/users/auth/token_ui.html"
WORKSPACE_CSS = ROOT / "mielenosoitukset_fi/static/css/user-workspace.css"


@pytest.mark.parametrize("method,path", [
    ("GET", "/users/auth/ui/tokens"),
    ("GET", "/users/auth/api_tokens/list"),
    ("POST", "/users/auth/api_token"),
    ("POST", "/users/auth/api_tokens/revoke"),
])
def test_token_manager_requires_authentication(client, db, seeded_data, method, path):
    before = list(db.api_tokens.find().sort("_id", 1))
    own_token = db.api_tokens.find_one({"user_id": seeded_data["user_id"]})
    response = client.open(path, method=method, json={
        "token_id": str(own_token["_id"]), "type": "short", "scopes": ["read"],
    })
    assert response.status_code == 302
    location = urlsplit(response.headers["Location"])
    assert location.path == "/users/auth/login"
    assert not location.netloc
    assert list(db.api_tokens.find().sort("_id", 1)) == before


def test_token_manager_renders_shared_accessible_contract(user_client):
    response = user_client.get("/users/auth/ui/tokens")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'class="container py-4 user-workspace-page"' in html
    assert 'class="user-page-heading"' in html
    assert 'class="user-data-list"' in html
    assert 'id="tokenModal"' in html
    assert 'id="tokenResultModal"' in html
    assert 'id="revokeTokenModal"' in html
    assert html.count('id="tokenModal"') == 1
    assert html.count('id="tokenResultModal"') == 1
    assert html.count('id="revokeTokenModal"') == 1
    assert 'aria-live="polite"' in html


def test_token_manager_uses_safe_dom_and_shared_styles():
    template = TOKEN_TEMPLATE.read_text(encoding="utf-8")
    css = WORKSPACE_CSS.read_text(encoding="utf-8")

    assert "<style" not in template
    assert "style=" not in template
    assert "innerHTML" not in template
    assert "confirm(" not in template
    assert "replaceChildren" in template
    assert "textContent" in template
    assert "bootstrap.Modal.getOrCreateInstance" in template
    assert "if (tokenCreationInProgress) event.preventDefault()" in template
    assert "showRevokeError(result.message || tokenMessages.revokeError)" in template
    assert 'id="revoke-token-error"' in template
    assert "window.clearInterval" not in template
    assert "Luo vastaava uusi token" in template
    assert ".user-page-heading" in css
    assert ".user-data-card" in css
    assert ".user-modal .modal-content" in css
    assert '.user-check-row .form-check-input[type="checkbox"]' in css


def test_token_manager_rendered_javascript_parses(user_client):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is unavailable")

    html = user_client.get("/users/auth/ui/tokens").get_data(as_text=True)
    scripts = re.findall(r"<script(?![^>]*src=)[^>]*>(.*?)</script>", html, re.S)
    token_script = next(script for script in scripts if "const tokenMessages" in script)
    result = subprocess.run(
        [node, "--check"],
        input=token_script,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_token_creation_rejects_malformed_scopes_with_localized_error(user_client, db):
    before = list(db.api_tokens.find().sort("_id", 1))
    response = user_client.post(
        "/users/auth/api_token",
        json={"type": "short", "scopes": "read"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "Tokenin käyttöoikeuksien pitää olla merkkijonolista."
    )
    assert list(db.api_tokens.find().sort("_id", 1)) == before


def test_token_revoke_rejects_invalid_and_foreign_ids(
    user_client, db, seeded_data
):
    before = list(db.api_tokens.find().sort("_id", 1))
    invalid = user_client.post(
        "/users/auth/api_tokens/revoke",
        json={"token_id": "not-an-object-id"},
    )
    foreign_token = db.api_tokens.find_one({"user_id": seeded_data["developer_id"]})
    foreign = user_client.post(
        "/users/auth/api_tokens/revoke",
        json={"token_id": str(foreign_token["_id"])},
    )

    assert invalid.status_code == 400
    assert invalid.get_json()["message"] == "Tokenin tunniste on virheellinen."
    assert foreign.status_code == 404
    assert foreign.get_json()["message"] == "Tokenia ei löytynyt."
    assert list(db.api_tokens.find().sort("_id", 1)) == before


def test_token_revoke_deletes_only_the_current_users_token(
    user_client, db, seeded_data
):
    # Start with usable credentials, including a second token owned by this user.
    raw_token, _ = create_token(user_id=seeded_data["user_id"], scopes=["read"])
    spare_token, _ = create_token(user_id=seeded_data["user_id"], scopes=["read"])
    own_token = check_token(raw_token)
    spare_record = check_token(spare_token)
    before = list(db.api_tokens.find().sort("_id", 1))

    response = user_client.post(
        "/users/auth/api_tokens/revoke",
        json={"token_id": str(own_token["_id"])},
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "success"
    assert list(db.api_tokens.find().sort("_id", 1)) == [
        token for token in before if token["_id"] != own_token["_id"]
    ]
    with pytest.raises(ApiException) as revoked:
        check_token(raw_token)
    assert revoked.value.status_code == 401
    assert revoked.value.message.code == "token_invalid"
    assert check_token(spare_token) == spare_record
