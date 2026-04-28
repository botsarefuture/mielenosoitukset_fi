from bson import ObjectId


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
            "route[]": ["Senate Square", "Railway Station"],
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/recu_demo/")

    created = db.recu_demos.find_one({"title": "Weekly recurring demo"})
    assert created is not None
    assert created["city"] == "Helsinki"
    assert created["route"] == ["Senate Square", "Railway Station"]
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
