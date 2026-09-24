"""Focused contracts for the canonical public profile editor."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETTINGS_TEMPLATE = ROOT / "mielenosoitukset_fi/templates/users/auth/settings.html"
WORKSPACE_CSS = ROOT / "mielenosoitukset_fi/static/css/user-workspace.css"


def test_profile_editor_uses_shared_optional_field_contract(user_client):
    response = user_client.get("/users/auth/settings")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    profile_form = html.split('id="tab-profile"', 1)[1].split(
        'id="tab-tokens"', 1
    )[0]

    assert 'class="user-form" id="profile-form"' in profile_form
    assert "user-form-section" in profile_form
    assert "user-field__control" in profile_form
    assert 'id="profile-pic"' in profile_form
    assert 'aria-describedby="profile-pic-help"' in profile_form
    assert "required" not in profile_form
    assert "Jätä kenttä tyhjäksi" in profile_form
    assert 'id="profile-submit"' in profile_form
    assert 'aria-live="polite"' in profile_form


def test_legacy_profile_editor_redirects_to_canonical_settings(user_client):
    response = user_client.get("/users/profile/edit")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/users/auth/settings")


def test_profile_api_requires_authentication(client):
    get_response = client.get("/users/auth/api/v2/user_profile")
    post_response = client.post(
        "/users/auth/api/v2/user_profile", json={"bio": "Not allowed"}
    )

    assert get_response.status_code == 302
    assert post_response.status_code == 302
    assert "/users/auth/login" in get_response.headers["Location"]
    assert "/users/auth/login" in post_response.headers["Location"]


def test_profile_api_preserves_picture_when_only_bio_changes(
    user_client, db, seeded_data
):
    original_picture = "https://cdn.example.test/profile-pics/original.png"
    db.users.update_one(
        {"_id": seeded_data["user_id"]},
        {"$set": {"profile_picture": original_picture}},
    )

    response = user_client.post(
        "/users/auth/api/v2/user_profile",
        json={"bio": "Updated public bio", "profile_picture": None},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert payload["data"] == {
        "bio": "Updated public bio",
        "profile_picture": original_picture,
    }
    stored = db.users.find_one({"_id": seeded_data["user_id"]})
    assert stored["bio"] == "Updated public bio"
    assert stored["profile_picture"] == original_picture


def test_profile_api_returns_safe_localized_validation_errors(user_client):
    invalid_json = user_client.post(
        "/users/auth/api/v2/user_profile",
        data="not-json",
        content_type="application/json",
    )
    invalid_image = user_client.post(
        "/users/auth/api/v2/user_profile",
        json={"bio": "Unchanged", "profile_picture": "not-valid-base64"},
    )

    assert invalid_json.status_code == 400
    assert invalid_json.get_json()["message"] == "Virheellinen pyyntö."
    assert invalid_image.status_code == 400
    assert invalid_image.get_json()["message"] == (
        "Profiilikuvan tiedot ovat virheelliset."
    )
    assert "base64" not in invalid_image.get_data(as_text=True).lower()


def test_profile_editor_uses_safe_dom_and_shared_css():
    template = SETTINGS_TEMPLATE.read_text(encoding="utf-8")
    profile_script = template.split(
        'const profileForm = document.getElementById("profile-form");', 1
    )[1].split("<!-- MFA QR Code Modal -->", 1)[0]
    message_script = template.split("function showSettingsMessage", 1)[1].split(
        "function hideSettingsMessage", 1
    )[0]
    css = WORKSPACE_CSS.read_text(encoding="utf-8")

    assert "innerHTML" not in message_script
    assert "innerHTML" not in profile_script
    assert "replaceChildren" in message_script
    assert "replaceChildren" in profile_script
    assert 'submitButton.setAttribute("aria-busy"' in profile_script
    assert "submitButton.disabled = isSubmitting" in profile_script
    assert ".user-form-section" in css
    assert ".user-field__control:focus-visible" in css
    assert not (ROOT / "mielenosoitukset_fi/templates/users/profile/edit_profile.html").exists()
    assert not (ROOT / "mielenosoitukset_fi/static/css/user/edit_profile.css").exists()
