"""Focused contracts for registration password validation and feedback."""

from pathlib import Path

from mielenosoitukset_fi.utils.helpers import is_strong_password


ROOT = Path(__file__).resolve().parents[1]
REGISTER_TEMPLATE = ROOT / "mielenosoitukset_fi/templates/users/auth/register.html"
WORKSPACE_CSS = ROOT / "mielenosoitukset_fi/static/css/user-workspace.css"
AUTH_ROUTES = ROOT / "mielenosoitukset_fi/users/BPs/auth.py"


def test_password_helper_ignores_empty_identity_fragments():
    accepted, _message = is_strong_password("Strong-Password")

    assert accepted is True


def test_password_helper_rejects_username_and_email_identity():
    includes_username, _message = is_strong_password(
        "My-alice-Password",
        username="alice",
        email="person@example.test",
    )
    includes_email, _message = is_strong_password(
        "My-person-Password",
        username="alice",
        email="person@example.test",
    )

    assert includes_username is False
    assert includes_email is False


def test_registration_rejects_weak_and_identity_based_passwords(client, db):
    weak_response = client.post(
        "/users/auth/register",
        data={
            "username": "weak-user",
            "email": "weak-user@example.test",
            "password": "password",
        },
    )
    identity_response = client.post(
        "/users/auth/register",
        data={
            "username": "identity-user",
            "email": "identity@example.test",
            "password": "Identity-user-Password",
        },
    )

    assert weak_response.status_code == 302
    assert identity_response.status_code == 302
    assert db.users.find_one({"username": "weak-user"}) is None
    assert db.users.find_one({"username": "identity-user"}) is None


def test_register_form_uses_safe_localized_shared_status_contract(client):
    response = client.get("/users/auth/register")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    template = REGISTER_TEMPLATE.read_text(encoding="utf-8")
    css = WORKSPACE_CSS.read_text(encoding="utf-8")

    assert "<style" not in template
    assert "style=" not in template
    assert "innerHTML" not in template
    assert 'document.createElement("style")' not in template
    assert "fonts.googleapis.com" not in template
    assert "cdnjs.cloudflare.com/ajax/libs/font-awesome" not in template
    assert "Boolean(emailIdentity)" in template
    assert "lowerPwd.includes(emailIdentity)" in template
    assert "replaceChildren" in template
    assert "|tojson" in template
    assert 'class="password-match user-inline-status"' in html
    assert ".user-inline-status--invalid" in css
    assert ".strength-meter-fill.strength-strong" in css


def test_auth_routes_unpack_password_validation_result():
    source = AUTH_ROUTES.read_text(encoding="utf-8")

    assert "if not is_strong_password(" not in source
    assert source.count("password_is_strong, _password_error = is_strong_password(") == 4
