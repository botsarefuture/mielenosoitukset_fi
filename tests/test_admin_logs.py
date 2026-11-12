from datetime import datetime

from mielenosoitukset_fi.admin.admin_bp import _format_log_entry


def test_admin_logs_page_is_a_linked_finnish_log_center(admin_client):
    response = admin_client.get("/admin/logs")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Hallinnan tapahtumaloki" in page
    assert "Lokit ja tapahtumat" in page
    assert "Mielenosoitushistoria" in page
    assert "Käyttöoikeushistoria" in page
    assert "Tekninen audit-loki" in page
    assert 'name="q"' in page
    assert 'name="category"' in page
    assert "Lokin katselu kirjataan" in page


def test_admin_logs_api_supports_search_and_event_categories(admin_client, db):
    db.admin_logs.insert_one(
        {
            "timestamp": datetime.utcnow(),
            "event": "organization_profile_updated",
            "request": {"method": "POST", "path": "/admin/organization/needle"},
            "user": {"username": "admin", "displayname": "Admin"},
        }
    )

    response = admin_client.get("/admin/api/logs?q=needle&category=change")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["total_logs"] == 1
    assert payload["logs"][0]["event"] == "organization_profile_updated"
    assert payload["logs"][0]["category"] == "change"


def test_admin_logs_page_paginates_server_rendered_rows_deterministically(
    admin_client, db
):
    timestamp = datetime.utcnow()
    db.admin_logs.insert_many(
        [
            {
                "timestamp": timestamp,
                "event": "collection_test_event",
                "request": {
                    "method": "GET",
                    "path": f"/admin/collection-marker-{index:02d}",
                },
                "actor": {"username": "admin", "displayname": "Admin"},
            }
            for index in range(45)
        ]
    )

    first = admin_client.get(
        "/admin/logs?q=collection-marker&page=1&per_page=20"
    )
    second = admin_client.get(
        "/admin/logs?q=collection-marker&page=2&per_page=20"
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_page = first.get_data(as_text=True)
    second_page = second.get_data(as_text=True)
    assert "collection-marker-44" in first_page
    assert "collection-marker-25" in first_page
    assert "collection-marker-24" not in first_page
    assert "collection-marker-25" not in second_page
    assert "collection-marker-24" in second_page
    assert "collection-marker-05" in second_page
    assert "45 osumaa" in second_page
    assert "q=collection-marker" in second_page
    assert "per_page=20" in second_page


def test_admin_logs_page_escapes_server_rendered_audit_content(admin_client, db):
    db.admin_logs.insert_one(
        {
            "timestamp": datetime.utcnow(),
            "event": "safe_render_marker",
            "details": '<img src=x onerror="alert(1)">',
            "request": {"method": "POST", "path": "/admin/safe-render"},
            "actor": {"username": "admin"},
        }
    )

    response = admin_client.get("/admin/logs?q=safe_render_marker")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "&lt;img src=x onerror=&#34;alert(1)&#34;&gt;" in page
    assert '<img src=x onerror="alert(1)">' not in page


def test_admin_log_payload_redacts_credentials_for_display():
    entry = _format_log_entry(
        {
            "timestamp": datetime.utcnow(),
            "request": {
                "method": "POST",
                "path": "/admin/user/save",
                "form": {
                    "username": "visible-user",
                    "password": "top-secret-password",
                    "csrf_token": "top-secret-csrf",
                },
            },
            "actor": {"id": "actor-1", "username": "admin"},
        }
    )

    form_data = entry["request_meta"]["form"]
    assert "visible-user" in form_data
    assert "top-secret-password" not in form_data
    assert "top-secret-csrf" not in form_data
    assert form_data.count("[REDACTED]") == 2
