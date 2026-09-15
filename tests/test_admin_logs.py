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
