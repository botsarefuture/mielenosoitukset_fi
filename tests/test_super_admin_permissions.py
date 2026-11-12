from bson import ObjectId

from mielenosoitukset_fi.users.models import User


def _user(*, role="user", global_admin=False):
    return User(
        user_id=ObjectId(),
        username="permission-test-user",
        password_hash="unused",
        role=role,
        global_admin=global_admin,
        global_permissions=[],
    )


def test_global_admin_flag_grants_every_permission_scope():
    user = _user(global_admin=True)

    assert user.has_permission("ANY_FUTURE_PERMISSION")
    assert user.has_permission("ANY_ORGANIZATION_PERMISSION", ObjectId())
    assert user.has_scoped_permission(
        "ANY_CITY_PERMISSION",
        scope_type="city",
        scope_key="helsinki",
    )
    assert user._perm_in("ANY_FUTURE_PERMISSION") == ["global"]


def test_super_admin_roles_grant_every_permission():
    for role in ("global_admin", "god", "superuser"):
        assert _user(role=role).has_permission("ANY_FUTURE_PERMISSION")


def test_god_role_also_enables_legacy_global_admin_checks_when_loaded():
    user = User.from_db(
        {
            "_id": ObjectId(),
            "username": "god-permission-test-user",
            "password_hash": "unused",
            "role": "god",
        }
    )

    assert user.global_admin is True
    assert user.has_permission("ANY_FUTURE_PERMISSION")


def test_regular_user_still_needs_an_explicit_permission():
    user = _user()

    assert not user.has_permission("ANY_FUTURE_PERMISSION")
