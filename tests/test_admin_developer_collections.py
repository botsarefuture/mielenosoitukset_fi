from datetime import datetime
from pathlib import Path

from bson import ObjectId


def _access_request(index, user_id):
    return {
        "_id": ObjectId(f"{index + 1:024x}"),
        "user_id": user_id,
        "reason": f"Access request {index:02d}",
        "status": "pending",
        "requested_at": datetime(2026, 9, 24, 10, 0, 0),
    }


def test_developer_requests_use_stable_server_pagination(
    admin_client, db, seeded_data
):
    db.api_token_requests.delete_many({})
    db.api_token_requests.insert_many(
        [_access_request(index, seeded_data["user_id"]) for index in range(25)]
    )

    first = admin_client.get(
        "/admin/developer/requests?kind=access&page=1&per_page=20"
    )
    second = admin_client.get(
        "/admin/developer/requests?kind=access&page=2&per_page=20"
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_page = first.get_data(as_text=True)
    second_page = second.get_data(as_text=True)
    assert "Access request 24" in first_page
    assert "Access request 05" in first_page
    assert "Access request 04" not in first_page
    assert "Access request 05" not in second_page
    assert "Access request 04" in second_page
    assert "Access request 00" in second_page
    assert "Näytetään 21–25 / 25 pyynnöstä" in second_page
    assert "kind=access" in second_page
    assert "per_page=20" in second_page


def test_developer_request_kind_and_status_filters_are_server_rendered(
    admin_client, db, seeded_data
):
    db.developer_scope_requests.delete_many({})
    app_id = seeded_data["app_id"]
    db.developer_scope_requests.insert_many(
        [
            {
                "_id": ObjectId(),
                "app_id": app_id,
                "user_id": seeded_data["developer_id"],
                "scopes": ["demo:read"],
                "reason": "Pending scope",
                "status": "pending",
                "requested_at": datetime(2026, 9, 24, 9, 0, 0),
            },
            {
                "_id": ObjectId(),
                "app_id": app_id,
                "user_id": seeded_data["developer_id"],
                "scopes": ["demo:write"],
                "reason": "Approved scope",
                "status": "approved",
                "requested_at": datetime(2026, 9, 24, 8, 0, 0),
            },
            {
                "_id": ObjectId(),
                "app_id": app_id,
                "user_id": seeded_data["developer_id"],
                "scopes": ["legacy:read"],
                "reason": "Legacy pending scope",
                "requested_at": datetime(2026, 9, 24, 7, 0, 0),
            },
        ]
    )

    response = admin_client.get(
        "/admin/developer/requests?kind=scope&status=pending&per_page=50"
    )

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Pending scope" in page
    assert "Legacy pending scope" in page
    assert "Approved scope" not in page
    assert "2 osumaa" in page
    assert "yhteensä 3 pyyntöä" in page
    assert "demo:read" in page
    assert "kind=scope" in page
    assert "status=pending" in page


def test_user_apps_use_stable_server_pagination(admin_client, db, seeded_data):
    owner_id = seeded_data["developer_id"]
    db.developer_apps.delete_many({"owner_id": owner_id})
    db.developer_apps.insert_many(
        [
            {
                "_id": ObjectId(f"{index + 1:024x}"),
                "owner_id": owner_id,
                "name": f"Developer app {index:02d}",
                "description": "Test app",
                "client_id": f"client-{index:02d}",
                "allowed_scopes": ["read"],
                "created_at": datetime(2026, 9, 24, 10, 0, 0),
            }
            for index in range(25)
        ]
    )

    response = admin_client.get(
        f"/admin/developer/user/{owner_id}/apps?page=2&per_page=20"
    )

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Developer app 04" in page
    assert "Developer app 00" in page
    assert "Developer app 05" not in page
    assert "Näytetään 21–25 / 25 sovelluksesta" in page


def test_developer_templates_use_shared_collection_contract():
    for relative_path in (
        "mielenosoitukset_fi/templates/admin_V2/developer/requests.html",
        "mielenosoitukset_fi/templates/admin_V2/developer/user_apps.html",
    ):
        source = Path(relative_path).read_text(encoding="utf-8")
        assert 'class="admin-page admin-workspace"' in source
        assert 'class="admin-data-view admin-data-view--scrollable"' in source
        assert 'class="admin-data-view__table"' in source
        assert "admin_pagination(" in source
        assert "table-responsive" not in source
        assert 'class="table ' not in source
        assert "text-muted" not in source
        assert "badge bg-" not in source

    requests = Path(
        "mielenosoitukset_fi/templates/admin_V2/developer/requests.html"
    ).read_text(encoding="utf-8")
    assert 'class="admin-filter-bar"' in requests
    assert 'class="admin-section-tabs"' in requests
    assert "alert(" not in requests
