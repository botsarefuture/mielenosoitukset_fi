import pytest
from pymongo.errors import DuplicateKeyError

from mielenosoitukset_fi.utils.validators import (
    is_reserved_identity_name,
    normalize_email,
    normalize_username,
    valid_username,
    validate_username,
)


@pytest.mark.parametrize("value", ["Admin", " admin ", "@Admin", "@ administrator "])
def test_reserved_admin_identity_is_case_and_prefix_insensitive(value):
    assert is_reserved_identity_name(value) is True


@pytest.mark.parametrize("value", ["admin helper", "administration", "user", None])
def test_non_reserved_identity_names_are_allowed(value):
    assert is_reserved_identity_name(value) is False


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


def test_normalize_email_is_case_and_whitespace_insensitive():
    assert normalize_email(" Emilia@Example.TEST ") == "emilia@example.test"


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


def test_registration_normalizes_email(client, db):
    response = client.post(
        "/users/auth/register",
        data={
            "username": "email-user",
            "email": " Email-User@Example.TEST ",
            "password": "StrongPassword123!",
        },
    )

    assert response.status_code == 302
    user = db.users.find_one({"username": "email-user"})
    assert user["email"] == "email-user@example.test"
    assert user["email_canonical"] == "email-user@example.test"


def test_registration_rejects_email_with_different_casing(client, db):
    response = client.post(
        "/users/auth/register",
        data={
            "username": "another-alice",
            "email": "ALICE@EXAMPLE.TEST",
            "password": "StrongPassword123!",
        },
    )

    assert response.status_code == 302
    assert db.users.find_one({"username": "another-alice"}) is None


@pytest.mark.parametrize(
    "canonical_field, canonical_value",
    [
        ("username_canonical", "database-unique-user"),
        ("email_canonical", "database-unique@example.test"),
    ],
)
def test_database_enforces_canonical_identity_uniqueness(
    db, canonical_field, canonical_value
):
    db.users.insert_one({canonical_field: canonical_value})

    with pytest.raises(DuplicateKeyError):
        db.users.insert_one({canonical_field: canonical_value})


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
