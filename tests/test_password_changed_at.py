"""SEC-04: password_changed_at, and the flag-gated invalidation after a reset."""

from datetime import datetime, timedelta, timezone

PASSWORD = "Zq7-correct-horse-battery-staple"


def _reset(client, token, password=PASSWORD):
    return client.post(
        f"/users/auth/password_reset/{token}",
        data={"password": password, "password_confirm": password},
    )


def _user(db):
    return db.users.find_one({"email": "alice@example.test"})


def test_reset_records_password_changed_at_without_touching_sessions_by_default(
    client, db, seeded_data
):
    epoch = _user(db).get("auth_epoch", 0)
    _reset(client, seeded_data["reset_token"])
    user = _user(db)
    assert user["password_changed_at"] is not None
    assert user.get("auth_epoch", 0) == epoch  # flag off: sessions stay valid


def test_flag_on_ends_existing_sessions_after_a_reset(app, client, db, seeded_data):
    app.config["INVALIDATE_ON_PASSWORD_RESET"] = True
    try:
        epoch = _user(db).get("auth_epoch", 0)
        _reset(client, seeded_data["reset_token"])
        assert _user(db)["auth_epoch"] == epoch + 1
    finally:
        app.config.pop("INVALIDATE_ON_PASSWORD_RESET", None)


def test_flag_on_refuses_reset_link_issued_before_the_last_change(
    app, client, db, seeded_data
):
    app.config["INVALIDATE_ON_PASSWORD_RESET"] = True
    try:
        db.users.update_one(
            {"email": "alice@example.test"},
            {"$set": {"password_changed_at": datetime.now(timezone.utc) + timedelta(seconds=5)}},
        )
        before = _user(db)["password_hash"]
        _reset(client, seeded_data["reset_token"])
        assert _user(db)["password_hash"] == before
        assert db.used_password_change_tokens.count_documents({}) == 0
    finally:
        app.config.pop("INVALIDATE_ON_PASSWORD_RESET", None)


def test_flag_off_keeps_older_reset_links_working(client, db, seeded_data):
    db.users.update_one(
        {"email": "alice@example.test"},
        {"$set": {"password_changed_at": datetime.now(timezone.utc) + timedelta(seconds=5)}},
    )
    before = _user(db)["password_hash"]
    _reset(client, seeded_data["reset_token"])
    assert _user(db)["password_hash"] != before


def test_accounts_without_the_field_behave_as_before(app, client, db, seeded_data):
    app.config["INVALIDATE_ON_PASSWORD_RESET"] = True
    try:
        db.users.update_one({"email": "alice@example.test"}, {"$unset": {"password_changed_at": ""}})
        before = _user(db)["password_hash"]
        _reset(client, seeded_data["reset_token"])
        assert _user(db)["password_hash"] != before
    finally:
        app.config.pop("INVALIDATE_ON_PASSWORD_RESET", None)


def test_token_age_helper_dates_legacy_tokens_from_expiry(app):
    import jwt

    from mielenosoitukset_fi.utils.auth import token_issued_before

    with app.app_context():
        exp = datetime.now(timezone.utc) + timedelta(minutes=30)  # issued ~30 min ago
        legacy = jwt.encode({"email": "a@x.test", "exp": exp}, app.config["SECRET_KEY"], algorithm="HS256")
        assert token_issued_before(legacy, datetime.now(timezone.utc)) is True
        assert token_issued_before(legacy, datetime.now(timezone.utc) - timedelta(hours=2)) is False
