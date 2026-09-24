from datetime import timedelta

import pytest
from bson import ObjectId

from mielenosoitukset_fi.admin.admin_demo_bp import collect_organizers
from mielenosoitukset_fi.users.models import User
from mielenosoitukset_fi.utils.time_utils import utcnow
from tests.conftest import _client_for_user


def _demo_form(title, *, city="Helsinki"):
    return {
        "title": title,
        "date": (utcnow().date() + timedelta(days=45)).isoformat(),
        "start_time": "12:00",
        "end_time": "14:00",
        "city": city,
        "address": "Testikatu 1",
        "type": "other",
        "description": "Organizer editor test",
    }


def test_organization_admin_only_sees_and_links_permitted_organizations(
    user_client, db, seeded_data
):
    db.users.update_one(
        {"_id": seeded_data["user_id"]}, {"$set": {"role": "admin"}}
    )
    own_org = db.organizations.find_one({"name": "Test Organization"})
    other_org = db.organizations.find_one({"name": "Verified Test Organization"})

    page = user_client.get("/admin/demo/create_demo")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert f'value="{own_org["_id"]}"' in html
    assert f'value="{other_org["_id"]}"' not in html

    permitted = _demo_form("Permitted organizer link")
    permitted.update(
        {
            "organizer_name_1": own_org["name"],
            "organizer_id_1": str(own_org["_id"]),
        }
    )
    response = user_client.post("/admin/demo/create_demo", data=permitted)
    assert response.status_code == 302
    created = db.demonstrations.find_one({"title": "Permitted organizer link"})
    assert created["organizers"][0]["organization_id"] == own_org["_id"]

    forged = _demo_form("Forged organizer link")
    forged.update(
        {
            "organizer_name_1": "Verified Test Organization",
            "organizer_id_1": str(other_org["_id"]),
        }
    )
    response = user_client.post("/admin/demo/create_demo", data=forged)
    assert response.status_code == 403
    assert db.demonstrations.find_one({"title": "Forged organizer link"}) is None


def test_create_demo_accepts_linked_and_freeform_organizers_with_sparse_indexes(
    admin_client, db
):
    linked_org = db.organizations.find_one({"name": "Test Organization"})
    form = _demo_form("Mixed organizer demonstration")
    form.update(
        {
            "organizer_name_2": linked_org["name"],
            "organizer_id_2": str(linked_org["_id"]),
            "organizer_name_5": "Vapaa järjestäjä",
            "organizer_email_5": "vapaa@example.test",
            "organizer_website_5": "https://vapaa.example.test",
            "organizer_show_name_5": "on",
            "organizer_show_email_5": "on",
        }
    )

    response = admin_client.post("/admin/demo/create_demo", data=form)
    assert response.status_code == 302
    created = db.demonstrations.find_one({"title": "Mixed organizer demonstration"})
    assert created is not None
    assert len(created["organizers"]) == 2
    assert created["organizers"][0]["organization_id"] == linked_org["_id"]
    assert created["organizers"][0]["name"] == linked_org["name"]
    assert created["organizers"][1]["organization_id"] is None
    assert created["organizers"][1]["name"] == "Vapaa järjestäjä"
    assert created["organizers"][1]["email"] == "vapaa@example.test"


def test_city_admin_can_add_freeform_but_cannot_forge_organization_link(
    app, db, seeded_data
):
    user_id = ObjectId()
    user_doc = User.create_user(
        username=f"organizer-city-{str(user_id)[-8:]}",
        password="CityPass1!",
        email=f"organizer-city-{str(user_id)[-8:]}@example.test",
        displayname="Organizer City Admin",
    )
    user_doc.update(
        {
            "_id": user_id,
            "confirmed": True,
            "active": True,
            "role": "city_admin",
            "global_admin": False,
            "global_permissions": [],
        }
    )
    db.users.insert_one(user_doc)
    db.admin_scope_grants.insert_one(
        {
            "user_id": user_id,
            "scope_type": "city",
            "scope_keys": ["helsinki"],
            "role": "city_reviewer",
            "permissions": ["CREATE_DEMO"],
        }
    )
    city_client = _client_for_user(app, user_id)

    page = city_client.get("/admin/demo/create_demo")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert 'data-organization-select' in html
    for organization in db.organizations.find({}, {"_id": 1}):
        assert f'value="{organization["_id"]}"' not in html

    freeform = _demo_form("City freeform organizer")
    freeform.update(
        {
            "organizer_name_3": "Kaupungin vapaa järjestäjä",
            "organizer_email_3": "city@example.test",
        }
    )
    assert city_client.post("/admin/demo/create_demo", data=freeform).status_code == 302
    assert db.demonstrations.find_one({"title": "City freeform organizer"}) is not None

    linked_org = db.organizations.find_one({"name": "Test Organization"})
    forged = _demo_form("City forged organizer")
    forged.update(
        {
            "organizer_name_1": linked_org["name"],
            "organizer_id_1": str(linked_org["_id"]),
        }
    )
    assert city_client.post("/admin/demo/create_demo", data=forged).status_code == 403
    assert db.demonstrations.find_one({"title": "City forged organizer"}) is None


def test_edit_demo_preserves_organizer_metadata_and_updates_freeform_fields(
    admin_client, db, seeded_data
):
    demo = db.demonstrations.find_one({"_id": seeded_data["demo_id"]})
    linked = demo["organizers"][0]
    linked["_id"] = ObjectId()
    linked["url"] = "/stored-organizer"
    free_record_id = ObjectId()
    demo["organizers"].append(
        {
            "_id": free_record_id,
            "name": "Vanha vapaa nimi",
            "email": "old@example.test",
            "website": "https://old.example.test",
            "organization_id": None,
        }
    )
    db.demonstrations.replace_one({"_id": demo["_id"]}, demo)

    form = _demo_form(demo["title"], city=demo["city"])
    form.update(
        {
            "approved": "on",
            "organizer_name_2": linked["name"],
            "organizer_id_2": str(linked["organization_id"]),
            "organizer_record_id_2": str(linked["_id"]),
            "organizer_name_7": "Päivitetty vapaa nimi",
            "organizer_email_7": "new@example.test",
            "organizer_website_7": "https://new.example.test",
            "organizer_record_id_7": str(free_record_id),
            "organizer_show_name_7": "on",
        }
    )
    response = admin_client.post(f"/admin/demo/edit_demo/{demo['_id']}", data=form)
    assert response.status_code == 302

    saved = db.demonstrations.find_one({"_id": demo["_id"]})
    assert len(saved["organizers"]) == 2
    assert saved["organizers"][0]["_id"] == linked["_id"]
    assert saved["organizers"][0]["organization_id"] == linked["organization_id"]
    assert saved["organizers"][1]["_id"] == free_record_id
    assert saved["organizers"][1]["name"] == "Päivitetty vapaa nimi"
    assert saved["organizers"][1]["email"] == "new@example.test"


def test_duplicate_organizers_are_rejected_server_side(app, db):
    linked_org = db.organizations.find_one({"name": "Test Organization"})
    with app.test_request_context(
        "/admin/demo/create_demo",
        method="POST",
        data={
            "organizer_name_1": linked_org["name"],
            "organizer_id_1": str(linked_org["_id"]),
            "organizer_name_4": linked_org["name"],
            "organizer_id_4": str(linked_org["_id"]),
        },
    ):
        from flask import request

        with pytest.raises(ValueError, match="Sama organisaatio"):
            collect_organizers(request)


@pytest.mark.parametrize(
    "row",
    (
        {"organizer_email_3": "missing-name@example.test"},
        {"organizer_website_3": "https://missing-name.example.test"},
        {"organizer_record_id_3": str(ObjectId())},
    ),
)
def test_incomplete_freeform_organizer_rows_are_rejected(app, row):
    with app.test_request_context(
        "/admin/demo/create_demo",
        method="POST",
        data={"organizer_name_3": "", **row},
    ):
        from flask import request

        with pytest.raises(ValueError, match="nimi on pakollinen"):
            collect_organizers(request)


def test_completely_unused_organizer_row_is_ignored(app):
    with app.test_request_context(
        "/admin/demo/create_demo",
        method="POST",
        data={
            "organizer_name_3": "",
            "organizer_email_3": "",
            "organizer_website_3": "",
            "organizer_id_3": "",
            "organizer_record_id_3": "",
        },
    ):
        from flask import request

        assert collect_organizers(request) == []
