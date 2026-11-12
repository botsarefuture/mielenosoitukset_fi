from datetime import datetime, timedelta
from pathlib import Path
import re

import pytest

from bson import ObjectId

from mielenosoitukset_fi.utils.time_utils import utcnow
from tests.conftest import _client_for_user


def _magic_link(index, *, action="preview", **overrides):
    now = utcnow()
    document = {
        "_id": ObjectId(f"{index + 1:024x}"),
        "token_hash": f"token-hash-{index:02d}",
        "action": action,
        "demo_id": f"demo-{index:02d}",
        "created_at": now,
        "expires_at": now + timedelta(days=1),
        "used_at": None,
        "revoked": False,
        "created_by": "test-admin",
    }
    document.update(overrides)
    return document


@pytest.mark.parametrize("tied_timestamps", [False, True])
def test_magic_token_collection_uses_stable_server_pagination(admin_client, db, tied_timestamps):
    db.magic_links.delete_many({})
    now = utcnow().replace(microsecond=0)
    # Insertion order, timestamp order and ID order must not accidentally agree.
    indices = list(range(0, 25, 2)) + list(range(1, 25, 2))
    db.magic_links.insert_many([
        _magic_link(index, created_at=now if tied_timestamps else now - timedelta(seconds=index))
        for index in indices
    ])
    expected = list(range(24, -1, -1)) if tied_timestamps else list(range(25))

    first = admin_client.get("/admin/demo/tokens?page=1&per_page=20")
    second = admin_client.get("/admin/demo/tokens?page=2&per_page=20")
    assert first.status_code == second.status_code == 200
    first_page = first.get_data(as_text=True)
    second_page = second.get_data(as_text=True)
    assert re.findall(r"token-hash-\d{2}", first_page) == [
        f"token-hash-{index:02d}" for index in expected[:20]
    ]
    assert re.findall(r"token-hash-\d{2}", second_page) == [
        f"token-hash-{index:02d}" for index in expected[20:]
    ]
    assert "Näytetään 21–25 / 25 linkistä" in second_page
    assert "per_page=20" in second_page


@pytest.mark.parametrize("query,expected", [
    ({"action": "approve"}, [5, 4, 3, 2, 1]),
    ({"status": "active"}, [2, 1, 0]),
    ({"status": "used"}, [4]),
    ({"status": "revoked"}, [5]),
])
def test_magic_token_filters_preserve_truthful_counts_and_page_size(admin_client, db, query, expected):
    db.magic_links.delete_many({})
    now = utcnow().replace(microsecond=0)
    records = [_magic_link(index, action="preview" if index == 0 else "approve",
        created_at=now - timedelta(seconds=6 - index)) for index in range(6)]
    records[3]["expires_at"] = now - timedelta(days=1)
    records[4]["used_at"] = now - timedelta(minutes=1)
    records[5].update(revoked=True, revoked_at=now - timedelta(minutes=2))
    db.magic_links.insert_many(records)

    response = admin_client.get("/admin/demo/tokens", query_string={**query, "page": 1, "per_page": 50})
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert f"{len(expected)} osumaa" in page
    assert "yhteensä 6 linkkiä" in page
    assert re.findall(r"token-hash-\d{2}", page) == [f"token-hash-{index:02d}" for index in expected]
    assert "per_page=50" in page
    assert all(f"{key}={value}" in page for key, value in query.items())


def test_magic_token_revocation_and_global_admin_boundary(app, admin_client, db, seeded_data):
    db.magic_links.delete_many({})
    target = _magic_link(0, demo_id=str(seeded_data["demo_id"]))
    neighbour = _magic_link(1, demo_id=str(seeded_data["demo_id"]))
    db.magic_links.insert_many([target, neighbour])
    original = db.magic_links.find_one({"_id": target["_id"]})
    original_neighbour = db.magic_links.find_one({"_id": neighbour["_id"]})

    csrf_token = _csrf_token(admin_client.get("/admin/demo/tokens"))
    response = admin_client.post("/admin/demo/tokens", data={"token_id": str(target["_id"]), "csrf_token": csrf_token})
    assert response.status_code == 302
    revoked = db.magic_links.find_one({"_id": target["_id"]})
    assert isinstance(revoked["revoked_at"], datetime)
    assert {key: value for key, value in revoked.items() if key != "revoked_at"} == {
        **original, "revoked": True,
    }
    assert db.magic_links.find_one({"_id": neighbour["_id"]}) == original_neighbour
    entries = list(db.demo_audit_logs.find({"action": "token_revoked", "details.token_id": str(target["_id"])}))
    assert len(entries) == 1
    assert entries[0]["demo_id"] == str(seeded_data["demo_id"])
    assert entries[0]["user_id"] == str(seeded_data["admin_id"])
    assert entries[0]["details"]["token_type"] == "preview"

    db.users.update_one({"_id": seeded_data["admin_id"]}, {"$set": {"role": "admin", "global_admin": False}})
    before_tokens = list(db.magic_links.find().sort("_id", 1))
    before_audit = list(db.demo_audit_logs.find().sort("_id", 1))
    assert admin_client.get("/admin/demo/tokens").status_code == 403
    for data in ({"token_id": str(neighbour["_id"])}, {"revoke_all": "1"}):
        denied = admin_client.post("/admin/demo/tokens", data={**data, "csrf_token": csrf_token})
        assert denied.status_code == 403
        assert list(db.magic_links.find().sort("_id", 1)) == before_tokens
        assert list(db.demo_audit_logs.find().sort("_id", 1)) == before_audit


def _csrf_token(response):
    assert response.status_code == 200
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
    assert match
    return match[1]


@pytest.mark.parametrize("revoke_all", [False, True])
def test_magic_token_revocation_requires_session_csrf(app, admin_client, db, seeded_data, revoke_all):
    db.magic_links.delete_many({})
    records = [_magic_link(index, demo_id=str(seeded_data["demo_id"])) for index in range(3)]
    records[2]["used_at"] = utcnow() - timedelta(minutes=1)
    db.magic_links.insert_many(records)
    data = {"revoke_all": "1"} if revoke_all else {"token_id": str(records[0]["_id"])}
    before = list(db.magic_links.find().sort("_id", 1))
    before_audit = list(db.demo_audit_logs.find().sort("_id", 1))

    missing = admin_client.post("/admin/demo/tokens", data=data)
    assert missing.status_code == 403
    assert list(db.magic_links.find().sort("_id", 1)) == before
    assert list(db.demo_audit_logs.find().sort("_id", 1)) == before_audit
    token = _csrf_token(admin_client.get("/admin/demo/tokens"))
    other = _client_for_user(app, seeded_data["admin_id"])
    foreign_token = _csrf_token(other.get("/admin/demo/tokens"))
    for invalid_token in ("wrong-token", "väärä", foreign_token):
        denied = admin_client.post("/admin/demo/tokens", data={**data, "csrf_token": invalid_token})
        assert denied.status_code == 403
        assert list(db.magic_links.find().sort("_id", 1)) == before
        assert list(db.demo_audit_logs.find().sort("_id", 1)) == before_audit

    allowed = admin_client.post("/admin/demo/tokens", data={**data, "csrf_token": token})
    assert allowed.status_code == 302
    assert db.magic_links.find_one({"_id": records[0]["_id"]})["revoked"] is True
    assert db.magic_links.find_one({"_id": records[1]["_id"]})["revoked"] is revoke_all
    assert db.magic_links.find_one({"_id": records[2]["_id"]}) == before[2]


def test_magic_token_template_uses_shared_collection_and_modal_contracts():
    source = (Path(__file__).resolve().parents[1] /
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/magic_tokens.html"
    ).read_text(encoding="utf-8")

    class_sets = [set(value.split()) for value in re.findall(r'\bclass="([^"]*)"', source)]
    for required in (
        {"admin-filter-bar"}, {"admin-active-filters"},
        {"admin-data-view", "admin-data-view--scrollable"},
        {"admin-data-view__table"}, {"modal", "fade", "admin-modal"},
    ):
        assert any(required <= classes for classes in class_sets), required
    assert "admin_pagination(" in source
    assert "onclick=" not in source
    assert "table-responsive" not in source
    assert 'class="table ' not in source
    assert "badge bg-" not in source
    assert "text-muted" not in source
