from datetime import timedelta
from pathlib import Path

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


def test_magic_token_collection_uses_stable_server_pagination(admin_client, db):
    db.magic_links.delete_many({})
    db.magic_links.insert_many([_magic_link(index) for index in range(25)])

    first = admin_client.get("/admin/demo/tokens?page=1&per_page=20")
    second = admin_client.get("/admin/demo/tokens?page=2&per_page=20")

    assert first.status_code == 200
    assert second.status_code == 200
    first_page = first.get_data(as_text=True)
    second_page = second.get_data(as_text=True)
    assert "token-hash-24" in first_page
    assert "token-hash-05" in first_page
    assert "token-hash-04" not in first_page
    assert "token-hash-05" not in second_page
    assert "token-hash-04" in second_page
    assert "token-hash-00" in second_page
    assert "Näytetään 21–25 / 25 linkistä" in second_page
    assert "per_page=20" in second_page


def test_magic_token_filters_preserve_truthful_counts_and_page_size(admin_client, db):
    db.magic_links.delete_many({})
    db.magic_links.insert_many(
        [
            _magic_link(0, action="preview"),
            _magic_link(1, action="approve"),
            _magic_link(2, action="approve"),
        ]
    )

    response = admin_client.get(
        "/admin/demo/tokens?action=approve&page=1&per_page=50"
    )

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "2 osumaa" in page
    assert "yhteensä 3 linkkiä" in page
    assert "token-hash-02" in page
    assert "token-hash-01" in page
    assert "token-hash-00" not in page
    assert "per_page=50" in page
    assert "action=approve" in page


def test_magic_token_revocation_and_global_admin_boundary(
    app, admin_client, db, seeded_data
):
    db.magic_links.delete_many({})
    token_id = db.magic_links.insert_one(_magic_link(0)).inserted_id

    response = admin_client.post(
        "/admin/demo/tokens", data={"token_id": str(token_id)}
    )

    assert response.status_code == 302
    assert db.magic_links.find_one({"_id": token_id})["revoked"] is True

    db.users.update_one(
        {"_id": seeded_data["user_id"]},
        {"$set": {"role": "admin", "global_admin": False}},
    )
    restricted_client = _client_for_user(app, seeded_data["user_id"])
    assert restricted_client.get("/admin/demo/tokens").status_code == 403


def test_magic_token_template_uses_shared_collection_and_modal_contracts():
    source = Path(
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/magic_tokens.html"
    ).read_text(encoding="utf-8")

    assert 'class="admin-filter-bar"' in source
    assert 'class="admin-active-filters"' in source
    assert 'class="admin-data-view admin-data-view--scrollable"' in source
    assert 'class="admin-data-view__table"' in source
    assert "admin_pagination(" in source
    assert 'class="modal fade admin-modal"' in source
    assert "onclick=" not in source
    assert "table-responsive" not in source
    assert 'class="table ' not in source
    assert "badge bg-" not in source
    assert "text-muted" not in source
