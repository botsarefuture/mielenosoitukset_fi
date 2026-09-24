"""Focused contracts for the registration next-steps flow."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "mielenosoitukset_fi/templates/users/auth/register_next_steps.html"
WORKSPACE_CSS = ROOT / "mielenosoitukset_fi/static/css/user-workspace.css"


def test_next_steps_without_session_email_is_safe(client):
    response = client.get("/users/auth/register/next_steps")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="resend_form"' not in html
    assert "Tapahtui virhe ja emme löydä sähköpostiasi" not in html
    assert "const resendForm = document.getElementById('resend_form');" in html
    assert "if (resendForm)" in html
    assert "const loopCheck = Boolean(verificationEmail);" in html


def test_next_steps_uses_session_email_and_safe_json(client):
    email = "person'quote@example.test"
    with client.session_transaction() as browser_session:
        browser_session["registration_email"] = email

    response = client.get("/users/auth/register/next_steps")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="resend_form"' in html
    assert "person&#39;quote@example.test" in html
    assert "person\\u0027quote@example.test" in html
    assert 'aria-current="step"' in html


def test_next_steps_uses_shared_components_without_page_owned_css():
    template = TEMPLATE.read_text(encoding="utf-8")
    css = WORKSPACE_CSS.read_text(encoding="utf-8")

    assert "<style" not in template
    assert "cdnjs.cloudflare.com/ajax/libs/font-awesome" not in template
    assert "fonts.googleapis.com" not in template
    assert "user-step-list" in template
    assert "resendButton.disabled = true" in template
    assert "window.clearInterval(verificationTimer)" in template
    assert "email|tojson" in template
    assert ".user-step--active .user-step__icon" in css
    assert ".user-step--complete .user-step__icon" in css


def test_resend_confirmation_does_not_expose_delivery_exception(
    user_client, db, seeded_data, monkeypatch
):
    from mielenosoitukset_fi.users.BPs import auth as auth_module

    db.users.update_one(
        {"_id": seeded_data["user_id"]},
        {"$set": {"confirmed": False}},
    )

    def fail_delivery(*args, **kwargs):
        raise RuntimeError("private mail transport details")

    monkeypatch.setattr(auth_module, "verify_emailer", fail_delivery)
    response = user_client.post(
        "/users/auth/resend_confirmation",
        data={"email_or_username": "alice@example.test"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert response.status_code == 500
    payload = response.get_json()
    assert payload == {
        "status": "error",
        "message": "Vahvistusviestin lähetys epäonnistui.",
    }
    assert "private mail transport details" not in response.get_data(as_text=True)
