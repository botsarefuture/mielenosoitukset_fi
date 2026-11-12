from copy import deepcopy

from bson import ObjectId

from mielenosoitukset_fi.users.models import User
from mielenosoitukset_fi.utils.cities import normalize_city_key
from tests.conftest import _client_for_user


def _insert_recurring_series(db, count=22):
    seed = db.recu_demos.find_one({"title": "Recurring Test Series"})
    assert seed is not None
    seed.pop("_id", None)
    documents = []
    for index in range(count):
        document = deepcopy(seed)
        document.update(
            {
                "_id": ObjectId(f"000000000000000000000{index + 1:03x}"),
                "title": f"Pagination recurring {index + 1:02d}",
                "date": "2026-06-01",
                "approved": index % 2 == 0,
            }
        )
        documents.append(document)
    db.recu_demos.insert_many(documents)


def test_recurring_control_paginates_with_stable_server_side_order(
    admin_client, db, seeded_data
):
    _insert_recurring_series(db)

    first = admin_client.get(
        "/admin/recu_demo/?search=Pagination+recurring&page=1&per_page=20"
    )
    second = admin_client.get(
        "/admin/recu_demo/?search=Pagination+recurring&page=2&per_page=20"
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_body = first.get_data(as_text=True)
    second_body = second.get_data(as_text=True)
    assert "Pagination recurring 01" in first_body
    assert "Pagination recurring 20" in first_body
    assert "Pagination recurring 21" not in first_body
    assert "Pagination recurring 21" in second_body
    assert "Pagination recurring 22" in second_body
    assert "Sivu 1 / 2" in first_body
    assert "Sivu 2 / 2" in second_body
    assert "search=Pagination+recurring" in second_body
    assert "per_page=20" in second_body


def test_recurring_control_filters_before_counting_and_pagination(
    admin_client, db, seeded_data
):
    _insert_recurring_series(db)

    response = admin_client.get(
        "/admin/recu_demo/?search=Pagination+recurring&approved=true&per_page=20"
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "11 osumaa" in body
    assert "Pagination recurring 01" in body
    assert "Pagination recurring 02" not in body
    assert "Rivejä sivulla" in body


def test_recurring_control_counts_and_lists_only_city_scoped_rows(
    app, db, seeded_data
):
    user_id = ObjectId()
    user_document = User.create_user(
        username="recurring-city-admin",
        password="CityPass1!",
        email="recurring-city-admin@example.test",
        displayname="Recurring City Admin",
    )
    user_document.update(
        {
            "_id": user_id,
            "confirmed": True,
            "active": True,
            "role": "city_admin",
            "global_admin": False,
            "global_permissions": [],
        }
    )
    db.users.insert_one(user_document)
    db.admin_scope_grants.insert_one(
        {
            "user_id": user_id,
            "scope_type": "city",
            "scope_keys": ["helsinki"],
            "permissions": ["LIST_RECURRING_DEMOS"],
        }
    )

    helsinki = db.recu_demos.find_one({"_id": seeded_data["recu_demo_id"]})
    db.recu_demos.update_one(
        {"_id": helsinki["_id"]},
        {"$set": {"city_key": normalize_city_key("Helsinki")}},
    )
    turku = deepcopy(helsinki)
    turku.update(
        {
            "_id": ObjectId(),
            "title": "Recurring Outside City Scope",
            "city": "Turku",
            "city_key": normalize_city_key("Turku"),
        }
    )
    db.recu_demos.insert_one(turku)

    response = _client_for_user(app, user_id).get("/admin/recu_demo/")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Recurring Test Series" in body
    assert "Recurring Outside City Scope" not in body
    assert "1 toistuvasta mielenosoituksesta" in body


def test_recu_demo_delete_accepts_json_confirmation_contract(admin_client, db, seeded_data):
    demo_id = seeded_data["recu_demo_id"]

    response = admin_client.post(
        f"/admin/recu_demo/delete_recu_demo/{demo_id}",
        json={"confirm_delete": True},
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "OK"
    assert db.recu_demos.count_documents({"_id": demo_id}) == 0


def test_recu_demo_delete_rejects_unconfirmed_json(admin_client, db, seeded_data):
    demo_id = seeded_data["recu_demo_id"]

    response = admin_client.post(
        f"/admin/recu_demo/delete_recu_demo/{demo_id}",
        json={},
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "ERROR"
    assert db.recu_demos.count_documents({"_id": demo_id}) == 1


def test_recurring_control_excludes_unrenderable_records_from_counts(
    admin_client, db, seeded_data
):
    seed = db.recu_demos.find_one({"_id": seeded_data["recu_demo_id"]})
    malformed = {
        **seed,
        "_id": ObjectId(),
        "title": "Broken recurring series",
        "repeat_schedule": "weekly",
    }
    db.recu_demos.insert_one(malformed)
    malformed_created_until = {
        **seed,
        "_id": ObjectId(),
        "title": "Broken created_until series",
        "created_until": "not-a-date",
    }
    db.recu_demos.insert_one(malformed_created_until)

    response = admin_client.get("/admin/recu_demo/")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Recurring Test Series" in body
    assert "Broken recurring series" not in body
    assert "Broken created_until series" not in body
    assert "Näytetään 1–1 / 1" in body
