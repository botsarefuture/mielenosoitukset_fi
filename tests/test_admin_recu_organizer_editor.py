from datetime import timedelta

from bson import ObjectId

from mielenosoitukset_fi.utils.time_utils import utcnow


def _recurring_form(title):
    return {
        "title": title,
        "description": "Recurring organizer editor test",
        "date": (utcnow().date() + timedelta(days=45)).isoformat(),
        "start_time": "12:00",
        "end_time": "14:00",
        "city": "Helsinki",
        "address": "Testikatu 1",
        "type": "STAY_STILL",
        "frequency_type": "weekly",
        "frequency_interval": "1",
    }


def test_organization_admin_only_sees_and_links_permitted_recurring_organizations(
    user_client, db, seeded_data
):
    db.users.update_one(
        {"_id": seeded_data["user_id"]}, {"$set": {"role": "admin"}}
    )
    db.memberships.update_one(
        {
            "user_id": seeded_data["user_id"],
            "organization_id": seeded_data["org_id"],
        },
        {
            "$addToSet": {
                "permissions": {
                    "$each": [
                        "CREATE_RECURRING_DEMO",
                        "EDIT_RECURRING_DEMO",
                    ]
                }
            }
        },
    )
    own_org = db.organizations.find_one({"_id": seeded_data["org_id"]})
    other_org = db.organizations.find_one({"name": "Verified Test Organization"})

    page = user_client.get("/admin/recu_demo/create_recu_demo")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert f'value="{own_org["_id"]}"' in html
    assert f'value="{other_org["_id"]}"' not in html

    permitted = _recurring_form("Permitted recurring organizer")
    permitted.update(
        {
            "organizer_name_1": own_org["name"],
            "organizer_id_1": str(own_org["_id"]),
        }
    )
    response = user_client.post("/admin/recu_demo/create_recu_demo", data=permitted)
    assert response.status_code == 302
    created = db.recu_demos.find_one({"title": "Permitted recurring organizer"})
    assert created["organizers"][0]["organization_id"] == own_org["_id"]

    forged = _recurring_form("Forged recurring organizer")
    forged.update(
        {
            "organizer_name_1": other_org["name"],
            "organizer_id_1": str(other_org["_id"]),
        }
    )
    response = user_client.post("/admin/recu_demo/create_recu_demo", data=forged)
    assert response.status_code == 403
    assert db.recu_demos.find_one({"title": "Forged recurring organizer"}) is None


def test_recurring_edit_preserves_organizer_metadata_without_mutating_children(
    admin_client, db, seeded_data
):
    parent = db.recu_demos.find_one({"_id": seeded_data["recu_demo_id"]})
    linked = parent["organizers"][0]
    linked["_id"] = ObjectId()
    linked["url"] = "/stored-recurring-organizer"
    freeform_id = ObjectId()
    parent["organizers"].append(
        {
            "_id": freeform_id,
            "name": "Vanha vapaa järjestäjä",
            "email": "old@example.test",
            "website": "https://old.example.test",
            "organization_id": None,
        }
    )
    db.recu_demos.replace_one({"_id": parent["_id"]}, parent)
    child_id = db.demonstrations.insert_one(
        {
            "title": "Organizer propagation sentinel",
            "parent": parent["_id"],
            "date": (utcnow().date() + timedelta(days=60)).isoformat(),
            "organizers": [{"name": "Existing child organizer"}],
        }
    ).inserted_id

    form = _recurring_form(parent["title"])
    form.update(
        {
            "approved": "on",
            "organizer_name_2": linked["name"],
            "organizer_id_2": str(linked["organization_id"]),
            "organizer_record_id_2": str(linked["_id"]),
            "organizer_name_7": "Päivitetty vapaa järjestäjä",
            "organizer_email_7": "new@example.test",
            "organizer_website_7": "https://new.example.test",
            "organizer_record_id_7": str(freeform_id),
            "organizer_show_name_7": "on",
        }
    )
    response = admin_client.post(
        f"/admin/recu_demo/edit_recu_demo/{parent['_id']}", data=form
    )
    assert response.status_code == 302

    saved = db.recu_demos.find_one({"_id": parent["_id"]})
    assert saved["organizers"][0]["_id"] == linked["_id"]
    assert saved["organizers"][0]["url"] == "/stored-recurring-organizer"
    assert saved["organizers"][1]["_id"] == freeform_id
    assert saved["organizers"][1]["name"] == "Päivitetty vapaa järjestäjä"
    child = db.demonstrations.find_one({"_id": child_id})
    assert child["organizers"] == [{"name": "Existing child organizer"}]

