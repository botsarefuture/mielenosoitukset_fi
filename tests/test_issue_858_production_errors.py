from pathlib import Path


def test_normal_user_does_not_see_admin_navigation(user_client):
    response = user_client.get("/")

    assert response.status_code == 200
    assert 'href="/admin/dashboard"' not in response.get_data(as_text=True)


def test_admin_user_sees_admin_navigation(admin_client):
    response = admin_client.get("/")

    assert response.status_code == 200
    assert 'href="/admin/dashboard"' in response.get_data(as_text=True)


def test_translator_sees_admin_navigation(translator_client):
    response = translator_client.get("/")

    assert response.status_code == 200
    assert 'href="/admin/dashboard"' in response.get_data(as_text=True)


def test_translation_permission_sees_admin_navigation(user_client, db, seeded_data):
    db.users.update_one(
        {"_id": seeded_data["user_id"]},
        {"$set": {"global_permissions": ["TRANSLATE_UI"]}},
    )

    response = user_client.get("/")

    assert response.status_code == 200
    assert 'href="/admin/dashboard"' in response.get_data(as_text=True)


def test_developer_requests_accepts_legacy_string_timestamp(
    admin_client, db, seeded_data
):
    db.api_token_requests.insert_one(
        {
            "user_id": seeded_data["user_id"],
            "status": "pending",
            "reason": "Legacy timestamp",
            "requested_at": "2026-09-27T08:15:00+00:00",
        }
    )

    response = admin_client.get("/admin/developer/requests?kind=access")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Legacy timestamp" in body
    assert "2026-09-27T08:15:00+00:00" in body


def test_developer_requests_remain_server_side_protected(user_client):
    response = user_client.get("/admin/developer/requests")

    assert response.status_code == 403


def test_apache_rate_limit_document_is_static_and_preserves_contract():
    root = Path(__file__).parents[1]
    page = (root / "deploy/apache/rate-limit.html").read_text(encoding="utf-8")
    config = (
        root / "deploy/apache/mielenosoitukset-rate-limit-vhost.conf"
    ).read_text(encoding="utf-8")

    assert "<script" not in page
    assert "temporary" in page
    assert 'ProxyPass "/__rate-limit.html" "!"' in config
    assert "/var/www/mielenosoitukset-error-pages/rate-limit.html" in config
    assert "ProxyErrorOverride Off" in config
    assert "ErrorDocument 403 /__rate-limit.html" in config
    assert 'Header always set Retry-After "60"' in config
