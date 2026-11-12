def test_flagged_user_is_redirected_to_identity_change(user_client, db, seeded_data):
    db.users.update_one(
        {"_id": seeded_data["user_id"]},
        {"$set": {"forced_identity_change": True}},
    )

    response = user_client.get("/", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/users/auth/forced_identity_change/")


def test_flagged_user_can_replace_both_names(user_client, db, seeded_data):
    db.users.update_one(
        {"_id": seeded_data["user_id"]},
        {
            "$set": {
                "username": "temporary-user",
                "displayname": "Temporary User",
                "forced_identity_change": True,
            }
        },
    )

    response = user_client.post(
        "/users/auth/forced_identity_change/",
        data={"username": "new-identity", "displayname": "New Identity"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    user = db.users.find_one({"_id": seeded_data["user_id"]})
    assert user["username"] == "new-identity"
    assert user["username_canonical"] == "new-identity"
    assert user["displayname"] == "New Identity"
    assert user["forced_identity_change"] is False


def test_flagged_user_cannot_choose_reserved_admin_identity(user_client, db, seeded_data):
    db.users.update_one(
        {"_id": seeded_data["user_id"]},
        {"$set": {"forced_identity_change": True}},
    )

    response = user_client.post(
        "/users/auth/forced_identity_change/",
        data={"username": "valid-user", "displayname": "@Admin"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    user = db.users.find_one({"_id": seeded_data["user_id"]})
    assert user["username"] == "alice"
    assert user["forced_identity_change"] is True


def test_identity_change_stays_forced_if_database_flag_was_cleared(
    user_client, db, seeded_data, monkeypatch
):
    from types import SimpleNamespace

    from mielenosoitukset_fi.users.BPs import auth as auth_module

    db.users.update_one(
        {"_id": seeded_data["user_id"]},
        {"$set": {"forced_identity_change": True}},
    )

    class NoMatchResult:
        matched_count = 0

    class NoMatchUsers:
        def find_one(self, *args, **kwargs):
            return db.users.find_one(*args, **kwargs)

        def update_one(self, *args, **kwargs):
            return NoMatchResult()

    monkeypatch.setattr(
        auth_module,
        "_get_mongo",
        lambda: SimpleNamespace(users=NoMatchUsers()),
    )

    response = user_client.post(
        "/users/auth/forced_identity_change/",
        data={"username": "new-identity", "displayname": "New Identity"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    user = db.users.find_one({"_id": seeded_data["user_id"]})
    assert user["username"] == "alice"
    assert user["forced_identity_change"] is True
