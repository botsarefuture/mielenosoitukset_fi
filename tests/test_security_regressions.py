def test_legacy_settings_rejects_privilege_fields(user_client, db, seeded_data):
    response = user_client.post(
        "/users/auth/api/v1/settings/",
        data={
            "language": "fi",
            "role": "global_admin",
            "global_admin": "true",
            "global_permissions": "EDIT_USER",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["rejected_fields"] == [
        "global_admin",
        "global_permissions",
        "role",
    ]

    user = db.users.find_one({"_id": seeded_data["user_id"]})
    assert user["role"] == "user"
    assert user["global_admin"] is False
    assert user["global_permissions"] == ["API_READ", "API_WRITE", "API_WRITE_DEMOS"]
    assert user.get("language") != "fi"


def test_legacy_settings_still_updates_allowed_fields(user_client, db, seeded_data):
    response = user_client.post(
        "/users/auth/api/v1/settings/",
        data={"language": "fi", "dark_mode": "true", "city": "Helsinki"},
    )

    assert response.status_code == 200
    user = db.users.find_one({"_id": seeded_data["user_id"]})
    assert user["language"] == "fi"
    assert user["dark_mode"] == "true"
    assert user["city"] == "Helsinki"


def test_ordinary_user_cannot_issue_mcp_admin_token(user_client, db, seeded_data):
    tokens_before = db.api_tokens.count_documents({"user_id": seeded_data["user_id"]})

    response = user_client.post(
        "/users/auth/api_token",
        json={"type": "short", "scopes": ["read", "mcp.admin"]},
    )

    assert response.status_code == 403
    assert db.api_tokens.count_documents({"user_id": seeded_data["user_id"]}) == tokens_before


def test_api_token_rejects_unknown_scopes(user_client, db, seeded_data):
    tokens_before = db.api_tokens.count_documents({"user_id": seeded_data["user_id"]})

    response = user_client.post(
        "/users/auth/api_token",
        json={"type": "short", "scopes": ["read", "totally.unknown"]},
    )

    assert response.status_code == 400
    assert db.api_tokens.count_documents({"user_id": seeded_data["user_id"]}) == tokens_before


def test_api_token_rejects_malformed_scope_payload(user_client, db, seeded_data):
    tokens_before = db.api_tokens.count_documents({"user_id": seeded_data["user_id"]})

    response = user_client.post(
        "/users/auth/api_token",
        json={"type": "short", "scopes": "mcp.admin"},
    )

    assert response.status_code == 400
    assert db.api_tokens.count_documents({"user_id": seeded_data["user_id"]}) == tokens_before


def test_global_admin_can_issue_mcp_admin_token(admin_client, db, seeded_data):
    response = admin_client.post(
        "/users/auth/api_token",
        json={"type": "short", "scopes": ["read", "mcp.admin"]},
    )

    assert response.status_code == 200
    assert response.get_json()["scopes"] == ["read", "mcp.admin"]
    token = db.api_tokens.find_one(
        {
            "user_id": seeded_data["admin_id"],
            "scopes": ["read", "mcp.admin"],
        }
    )
    assert token is not None


def test_auth_security_routes_ignore_stale_module_database_handle(
    monkeypatch,
    user_client,
    db,
    seeded_data,
):
    import mielenosoitukset_fi.users.BPs.auth as auth_module

    class StaleUsers:
        def find_one(self, *args, **kwargs):
            return None

        def update_one(self, *args, **kwargs):
            return None

    class StaleDatabase:
        users = StaleUsers()

    monkeypatch.setattr(auth_module, "mongo", StaleDatabase())

    unknown_scope_response = user_client.post(
        "/users/auth/api_token",
        json={"type": "short", "scopes": ["read", "totally.unknown"]},
    )
    settings_response = user_client.post(
        "/users/auth/api/v1/settings/",
        data={"language": "fi", "dark_mode": "true", "city": "Helsinki"},
    )

    assert unknown_scope_response.status_code == 400
    assert settings_response.status_code == 200
    user = db.users.find_one({"_id": seeded_data["user_id"]})
    assert user["language"] == "fi"
    assert user["dark_mode"] == "true"
    assert user["city"] == "Helsinki"
