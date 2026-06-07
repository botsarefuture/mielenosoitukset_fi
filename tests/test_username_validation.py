import pytest

from mielenosoitukset_fi.utils.validators import (
    normalize_username,
    valid_username,
    validate_username,
)


@pytest.mark.parametrize(
    "raw_username, normalized",
    [
        (" alice ", "alice"),
        ("Alice-123", "alice-123"),
        ("USER_name", "user_name"),
    ],
)
def test_normalize_username(raw_username, normalized):
    assert normalize_username(raw_username) == normalized


def test_normalize_username_rejects_non_string_values():
    assert normalize_username(None) == ""
    assert normalize_username(123) == ""


@pytest.mark.parametrize(
    "username",
    [
        "alice",
        "alice-123",
        "alice_test",
        "123",
    ],
)
def test_validate_username_accepts_supported_usernames(username):
    assert validate_username(username) == (True, "")


@pytest.mark.parametrize(
    "username",
    [
        "",
        "ab",
        "a" * 31,
        "admin",
        "_alice",
        "alice-",
        "alice smith",
        "älice",
        "alice--smith",
        "alice_-smith",
    ],
)
def test_validate_username_rejects_unsupported_usernames(username):
    valid, message = validate_username(username)

    assert valid is False
    assert message


def test_valid_username_provides_boolean_validator_api():
    assert valid_username("alice") is True
    assert valid_username("alice smith") is False
    assert valid_username(None) is False


def test_username_availability_rejects_invalid_username(client):
    response = client.get("/users/auth/api/username_free?username=alice%20smith")

    assert response.status_code == 400
    assert response.get_json()["available"] is False


def test_username_availability_is_case_insensitive_for_existing_users(client):
    response = client.get("/users/auth/api/username_free?username=Alice")

    assert response.status_code == 200
    assert response.get_json()["available"] is False


def test_registration_normalizes_username(client, db):
    response = client.post(
        "/users/auth/register",
        data={
            "username": " New-User ",
            "email": "new-user@example.test",
            "password": "StrongPassword123!",
        },
    )

    assert response.status_code == 302
    user = db.users.find_one({"username": "new-user"})
    assert user is not None
    assert user["username_canonical"] == "new-user"
    assert db.users.find_one({"username": " New-User "}) is None


def test_login_normalizes_username(client, db):
    response = client.post(
        "/users/auth/login",
        data={"username": " ALICE ", "password": "UserPass1!"},
    )

    assert response.status_code == 302
    with client.session_transaction() as session:
        assert session["_user_id"] == str(db.users.find_one({"username": "alice"})["_id"])


def test_mfa_check_normalizes_username(client):
    response = client.post(
        "/users/auth/2fa_check",
        data={"username": " ALICE ", "password": "UserPass1!"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"enabled": False, "valid": True}


def test_login_supports_legacy_mixed_case_username(client, db):
    db.users.update_one(
        {"username": "alice"},
        {"$set": {"username": "LegacyAlice"}, "$unset": {"username_canonical": ""}},
    )

    response = client.post(
        "/users/auth/login",
        data={"username": "legacyalice", "password": "UserPass1!"},
    )

    assert response.status_code == 302
    with client.session_transaction() as session:
        assert session["_user_id"] == str(
            db.users.find_one({"username": "LegacyAlice"})["_id"]
        )


def test_mfa_check_supports_legacy_mixed_case_username(client, db):
    db.users.update_one(
        {"username": "alice"},
        {"$set": {"username": "LegacyAlice"}, "$unset": {"username_canonical": ""}},
    )

    response = client.post(
        "/users/auth/2fa_check",
        data={"username": "LEGACYALICE", "password": "UserPass1!"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"enabled": False, "valid": True}
