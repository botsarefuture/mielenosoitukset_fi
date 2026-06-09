from bson import ObjectId
from mielenosoitukset_fi.utils.classes import RecurringDemonstration


def test_recurring_demo_from_dict_accepts_city_key(seeded_data, db):
    recu_demo = db.recu_demos.find_one({"_id": seeded_data["recu_demo_id"]})
    recu_demo["city_key"] = "helsinki"

    parsed = RecurringDemonstration.from_dict(recu_demo)

    assert parsed.city == "Helsinki"


def test_admin_can_create_recurring_demo_with_create_form_fields(admin_client, db):
    response = admin_client.post(
        "/admin/recu_demo/create_recu_demo",
        data={
            "title": "Weekly recurring demo",
            "description": "Created through the admin create form.",
            "date": "2026-05-01",
            "start_time": "12:00",
            "end_time": "13:00",
            "city": "Helsinki",
            "address": "Testikatu 1",
            "type": "MARCH",
            "approved": "on",
            "organizer_name_1": "Test Org",
            "organizer_id_1": str(ObjectId()),
            "recurrence_type": "WEEKLY",
            "recurrence_interval": "2",
            "recurrence_end_date": "2026-06-01",
            "route[]": ["Senate Square", "Railway Station", "Senate Square"],
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/recu_demo/")

    created = db.recu_demos.find_one({"title": "Weekly recurring demo"})
    assert created is not None
    assert created["city"] == "Helsinki"
    assert created["route"] == ["Senate Square", "Railway Station", "Senate Square"]
    assert created["recurs"] is True
    assert created["repeat_schedule"]["frequency"] == "weekly"
    assert created["repeat_schedule"]["interval"] == 2
    assert created["repeat_schedule"]["end_date"] == "2026-06-01"


def test_admin_can_create_recurring_demo_with_sparse_organizer_indexes(admin_client, db):
    kept_org_id = ObjectId()

    response = admin_client.post(
        "/admin/recu_demo/create_recu_demo",
        data={
            "title": "Sparse organizer recurring demo",
            "description": "Organizer indexes should not need to be contiguous.",
            "date": "2026-05-02",
            "start_time": "14:00",
            "end_time": "15:00",
            "city": "Helsinki",
            "address": "Testikatu 2",
            "type": "STAY_STILL",
            "organizer_name_2": "Existing Organization",
            "organizer_id_2": str(kept_org_id),
            "frequency_type": "none",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    created = db.recu_demos.find_one({"title": "Sparse organizer recurring demo"})
    assert created is not None
    assert len(created["organizers"]) == 1
    assert created["organizers"][0]["name"] == "Existing Organization"
    assert created["organizers"][0]["organization_id"] == kept_org_id


def test_admin_can_bulk_update_selected_recurring_children(admin_client, db, seeded_data):
    parent_id = seeded_data["recu_demo_id"]
    selected_id = ObjectId()
    untouched_id = ObjectId()
    outsider_id = ObjectId()
    db.demonstrations.insert_many(
        [
            {
                "_id": selected_id,
                "parent": parent_id,
                "title": "Old selected title",
                "date": "2026-07-01",
                "start_time": "10:00",
                "end_time": "11:00",
                "city": "Espoo",
                "city_key": "espoo",
                "address": "Old address",
                "tags": ["old"],
            },
            {
                "_id": untouched_id,
                "parent": parent_id,
                "title": "Untouched child",
                "date": "2026-07-08",
                "city": "Espoo",
                "tags": ["old"],
            },
            {
                "_id": outsider_id,
                "parent": ObjectId(),
                "title": "Outsider child",
                "date": "2026-07-08",
                "city": "Espoo",
                "tags": ["old"],
            },
        ]
    )

    response = admin_client.post(
        f"/admin/recu_demo/{parent_id}/bulk-update-children",
        data={
            "child_ids": [str(selected_id), str(outsider_id)],
            "fields": ["title", "location", "tags"],
            "freeze_after_update": "on",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    selected = db.demonstrations.find_one({"_id": selected_id})
    untouched = db.demonstrations.find_one({"_id": untouched_id})
    outsider = db.demonstrations.find_one({"_id": outsider_id})
    parent = db.recu_demos.find_one({"_id": parent_id})

    assert selected["title"] == "Recurring Test Series"
    assert selected["city"] == "Helsinki"
    assert selected["address"] == "Kaivokatu 1, Helsinki"
    assert selected["tags"] == ["test-tag"]
    assert untouched["title"] == "Untouched child"
    assert outsider["title"] == "Outsider child"
    assert str(selected_id) in parent["freezed_children"]
    assert db.demo_edit_history.count_documents({"demo_id": str(selected_id)}) == 1


def test_recurring_demo_no_change_save_preserves_schedule_and_nullable_values(
    admin_client, db, seeded_data
):
    recu_demo_id = seeded_data["recu_demo_id"]
    organizer_id = ObjectId()
    db.recu_demos.update_one(
        {"_id": recu_demo_id},
        {
            "$set": {
                "start_time": "18:00:00",
                "end_time": "20:00:00",
                "description": None,
                "facebook": None,
                "cover_picture": None,
                "gallery_images": None,
                "route": None,
                "repeat_schedule": {
                    "frequency": "weekly",
                    "interval": 2,
                    "weekday": "friday",
                    "monthly_option": None,
                    "day_of_month": None,
                    "nth_weekday": None,
                    "weekday_of_month": None,
                    "end_date": "9999-12-31",
                    "as_string": "every 2 weeks on Friday",
                },
                "organizers": [
                    {
                        "_id": organizer_id,
                        "name": "Stored organizer",
                        "email": "stored@example.test",
                        "website": "",
                        "organization_id": None,
                        "url": "/stored-organizer",
                        "is_private": True,
                        "show_name_public": True,
                        "show_email_public": False,
                    }
                ],
            }
        },
    )

    response = admin_client.post(
        f"/admin/recu_demo/edit_recu_demo/{recu_demo_id}",
        data={
            "title": "Recurring Test Series",
            "description": "",
            "date": "2026-05-08",
            "start_time": "18:00",
            "end_time": "20:00",
            "facebook": "",
            "city": "Helsinki",
            "address": "Kaivokatu 1, Helsinki",
            "type": "STAY_STILL",
            "approved": "on",
            "cover_picture": "",
            "gallery_images": "",
            "frequency_type": "weekly",
            "frequency_interval": "2",
            "weekday": "friday",
            "end_date": "9999-12-31",
            "organizer_name_1": "Stored organizer",
            "organizer_record_id_1": str(organizer_id),
            "organizer_email_1": "stored@example.test",
            "organizer_website_1": "",
            "organizer_is_private_1": "on",
            "organizer_show_name_1": "on",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    saved = db.recu_demos.find_one({"_id": recu_demo_id})
    assert saved["start_time"] == "18:00:00"
    assert saved["end_time"] == "20:00:00"
    assert saved["description"] is None
    assert saved["facebook"] is None
    assert saved["cover_picture"] is None
    assert saved["gallery_images"] is None
    assert saved["route"] is None
    assert saved["repeat_schedule"]["frequency"] == "weekly"
    assert saved["repeat_schedule"]["interval"] == 2
    assert saved["repeat_schedule"]["weekday"] == "friday"
    assert saved["repeat_schedule"]["end_date"] == "9999-12-31"
    assert saved["organizers"][0]["_id"] == organizer_id
    assert saved["organizers"][0]["url"] == "/stored-organizer"
    assert saved["organizers"][0]["is_private"] is True
    assert saved["organizers"][0]["show_email_public"] is False
