"""City admin applications: case delivery, local visibility and global decisions."""

from bson import ObjectId

from mielenosoitukset_fi.utils.city_admin_applications import deliver_pending
from mielenosoitukset_fi.utils.time_utils import utcnow
from tests.conftest import _client_for_user
from tests.test_city_scoped_admin import _create_scoped_admin


def _application(db, applicant, cities):
    doc = {
        "_id": ObjectId(), "user_id": applicant, "city_keys": cities,
        "about": "Olen järjestänyt mielenosoituksia kymmenen vuotta ja haluan auttaa.",
        "activism": {"cities": cities, "organizations": "Paikallinen ryhmä", "experience": "some",
                     "experience_details": ""},
        "references": "", "status": "received", "case_pending": True,
        "consent_at": utcnow(), "created_at": utcnow(), "updated_at": utcnow(),
    }
    db.city_admin_applications.insert_one(doc)
    return doc["_id"]


def test_delivery_creates_one_case_per_application(db, seeded_data):
    applicant = seeded_data["user_id"]
    application = _application(db, applicant, ["tampere"])

    assert deliver_pending(db) == 1
    assert deliver_pending(db) == 0

    case = db.cases.find_one({"_id": application})
    assert case["type"] == "city_admin_application"
    assert case["meta"]["city_keys"] == ["tampere"]
    # The case points to the application; the free text is not copied.
    assert "about" not in repr(case.get("suggestion"))
    stored = db.city_admin_applications.find_one({"_id": application})
    assert stored["case_pending"] is False and stored["case_id"] == application


def test_local_admins_see_only_their_cities_and_cannot_decide(app, db, seeded_data):
    applicant = seeded_data["user_id"]
    own = _application(db, applicant, ["tampere"])
    foreign = _application(db, applicant, ["turku"])
    deliver_pending(db)
    local = _create_scoped_admin(db, ["tampere"], ["LIST_CASES", "VIEW_CASE", "EDIT_CASE"])
    client = _client_for_user(app, local)

    page = client.get(f"/admin/case/{own}/")
    assert page.status_code == 200
    assert "Olen järjestänyt mielenosoituksia" in page.get_data(as_text=True)
    assert client.get(f"/admin/case/{foreign}/").status_code == 403

    response = client.post(f"/admin/case/{own}/application_status/", data={"status": "approved"})
    assert response.status_code == 403
    assert db.city_admin_applications.find_one({"_id": own})["status"] == "received"


def test_global_admin_decision_closes_the_case_without_granting_rights(admin_client, db, seeded_data):
    applicant = seeded_data["user_id"]
    before_role = db.users.find_one({"_id": applicant}).get("role")
    application = _application(db, applicant, ["tampere"])
    deliver_pending(db)

    response = admin_client.post(f"/admin/case/{application}/application_status/", data={"status": "approved"})
    assert response.status_code == 302
    assert db.city_admin_applications.find_one({"_id": application})["status"] == "approved"
    case = db.cases.find_one({"_id": application})
    assert case["meta"]["closed"] is True
    assert case["case_history"][-1]["mech_action"] == "application_status"
    assert db.users.find_one({"_id": applicant}).get("role") == before_role
    assert not db.admin_scope_grants.find_one({"user_id": applicant, "revoked_at": None, "scope_keys": "tampere"})

    bad = admin_client.post(f"/admin/case/{application}/application_status/", data={"status": "withdrawn"})
    assert bad.status_code == 302
    assert db.city_admin_applications.find_one({"_id": application})["status"] == "approved"


def test_delivery_stays_pending_while_the_national_team_has_nobody_to_notify(db, seeded_data, monkeypatch):
    from mielenosoitukset_fi.utils import city_admin_applications as module

    def unavailable(_db):
        raise RuntimeError("National administration team has no eligible recipients")

    monkeypatch.setattr(module, "national_recipients", unavailable)
    application = _application(db, seeded_data["user_id"], ["tampere"])
    assert deliver_pending(db) == 0
    assert db.cases.find_one({"_id": application})  # the case itself exists
    assert db.city_admin_applications.find_one({"_id": application})["case_pending"] is True

    admin = seeded_data["admin_id"]
    monkeypatch.setattr(module, "national_recipients", lambda _db: [{"user_id": str(admin), "email": "a@example.org"}])
    assert deliver_pending(db) == 1
    notice = db.notifications.find_one({"_id": f"city-admin-application:{application}:{admin}"})
    from mielenosoitukset_fi.utils.notifications import serialize_notification
    assert serialize_notification(notice)["message"] == "Uusi kaupunkiadminhakemus: Tampere"
