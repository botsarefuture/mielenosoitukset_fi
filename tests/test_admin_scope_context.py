from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch
from bson import ObjectId

from mielenosoitukset_fi.admin.admin_bp import (
    _admin_actor_context,
    inject_admin_actor_context,
)
from mielenosoitukset_fi.users.models import User
from tests.conftest import _client_for_user


def _user(**overrides):
    values = {
        "is_authenticated": True,
        "role": "user",
        "global_admin": False,
        "global_permissions": [],
        "admin_scope_grants": [],
        "memberships": [],
    }
    values.update(overrides)
    values[
        "has_full_permissions"
    ] = bool(values["global_admin"]) or values["role"] in {
        "global_admin",
        "god",
        "superuser",
    }
    return SimpleNamespace(**values)


def test_admin_actor_context_distinguishes_global_city_and_translator_roles():
    assert _admin_actor_context(_user(global_admin=True)) == {"kind": "global"}
    assert _admin_actor_context(
        _user(
            role="city_admin",
            admin_scope_grants=[
                {
                    "scope_type": "city",
                    "scope_keys": ["helsinki", "turku"],
                    "permissions": ["LIST_DEMOS"],
                }
            ],
        )
    ) == {"kind": "city", "city_names": ["Helsinki", "Turku"]}
    assert _admin_actor_context(_user(role="translator")) == {
        "kind": "translator"
    }


def test_admin_role_with_limited_permissions_is_not_classified_as_global():
    limited_admin = _user(
        role="admin",
        global_admin=False,
        global_permissions=["API_READ"],
    )
    assert _admin_actor_context(limited_admin) == {"kind": "restricted"}


def test_admin_actor_context_distinguishes_organization_and_restricted_roles():
    organization_context = _admin_actor_context(
        _user(
            memberships=[
                SimpleNamespace(role="owner"),
                SimpleNamespace(role="admin"),
                SimpleNamespace(role="member"),
            ]
        )
    )

    assert organization_context == {
        "kind": "organization",
        "organization_count": 2,
    }
    assert _admin_actor_context(_user()) == {"kind": "restricted"}


def test_admin_shell_does_not_claim_every_actor_is_a_superuser():
    source = Path("mielenosoitukset_fi/templates/admin_base.html").read_text(
        encoding="utf-8"
    )

    assert "Olet superkäyttäjätilassa" not in source
    assert "admin-scope-context--{{ admin_actor_context.kind }}" in source
    for kind in (
        "Globaali ylläpito",
        "Kaupunkiadmin",
        "Organisaatioylläpitäjä",
        "Kääntäjä",
        "Rajattu ylläpito",
    ):
        assert kind in source


def test_public_pages_do_not_evaluate_admin_scope_context(app, db, seeded_data):
    client = _client_for_user(app, seeded_data["user_id"])
    with patch(
        "mielenosoitukset_fi.admin.admin_bp._admin_actor_context"
    ) as spy:
        response = client.get("/")

    assert response.status_code == 200
    spy.assert_not_called()


def test_public_context_processor_returns_no_admin_scope_context(app):
    with app.test_request_context("/"):
        context = inject_admin_actor_context()

    assert context == {}


def test_admin_shell_renders_the_authenticated_scope(app, admin_client, db, seeded_data):
    global_page = admin_client.get("/admin/demo/").get_data(as_text=True)
    assert "Globaali ylläpito" in global_page
    assert "Kaikki ylläpito-oikeudet" in global_page

    city_admin_id = ObjectId()
    city_admin = User.create_user(
        username="scope-context-city-admin",
        password="CityPass1!",
        email="scope-context-city-admin@example.test",
        displayname="Scope Context City Admin",
    )
    city_admin.update(
        {
            "_id": city_admin_id,
            "confirmed": True,
            "active": True,
            "role": "city_admin",
            "global_admin": False,
            "global_permissions": [],
        }
    )
    db.users.insert_one(city_admin)
    db.admin_scope_grants.insert_one(
        {
            "user_id": city_admin_id,
            "scope_type": "city",
            "scope_keys": ["helsinki"],
            "permissions": ["LIST_DEMOS"],
        }
    )

    city_page = _client_for_user(app, city_admin_id).get("/admin/demo/")
    assert city_page.status_code == 200
    city_body = city_page.get_data(as_text=True)
    assert "Kaupunkiadmin" in city_body
    assert "Helsinki" in city_body
    assert "Globaali ylläpito" not in city_body
