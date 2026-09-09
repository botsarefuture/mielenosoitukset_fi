from datetime import timedelta
from urllib.parse import urlsplit


CSRF_SESSION_KEY = "demo_edit_link_csrf_token"


def _csrf_headers(client):
    with client.session_transaction() as session:
        session[CSRF_SESSION_KEY] = "edit-link-test-csrf"
    return {"X-CSRF-Token": "edit-link-test-csrf"}


def _token_from_url(edit_link):
    return urlsplit(edit_link).path.rsplit("/", 1)[-1]


def test_edit_link_duration_is_allowlisted_and_registry_expiry_matches(
    admin_client, db, seeded_data
):
    response = admin_client.post(
        f"/admin/demo/generate_edit_link/{seeded_data['demo_id']}",
        json={"duration": "1h"},
        headers=_csrf_headers(admin_client),
    )

    assert response.status_code == 200
    payload = response.get_json()
    token = _token_from_url(payload["edit_link"])
    from mielenosoitukset_fi.admin.admin_demo_bp import _hash_token

    token_doc = db.magic_links.find_one({"token_hash": _hash_token(token)})
    assert token_doc["duration_seconds"] == 3600
    assert token_doc["expires_at"] - token_doc["created_at"] == timedelta(hours=1)
    assert payload["expires_at"] == token_doc["expires_at"].isoformat()

    rejected = admin_client.post(
        f"/admin/demo/generate_edit_link/{seeded_data['demo_id']}",
        json={"duration": "30d"},
        headers=_csrf_headers(admin_client),
    )
    assert rejected.status_code == 400


def test_each_edit_link_is_unique_and_revocation_blocks_anonymous_access(
    app, admin_client, db, seeded_data
):
    headers = _csrf_headers(admin_client)
    first = admin_client.post(
        f"/admin/demo/generate_edit_link/{seeded_data['demo_id']}",
        json={"duration": "24h"},
        headers=headers,
    ).get_json()
    second = admin_client.post(
        f"/admin/demo/generate_edit_link/{seeded_data['demo_id']}",
        json={"duration": "24h"},
        headers=headers,
    ).get_json()

    assert first["edit_link"] != second["edit_link"]
    first_path = urlsplit(first["edit_link"]).path
    assert app.test_client().get(first_path).status_code == 200

    from mielenosoitukset_fi.admin.admin_demo_bp import _hash_token

    token_doc = db.magic_links.find_one(
        {"token_hash": _hash_token(_token_from_url(first["edit_link"]))}
    )
    revoked = admin_client.post(
        f"/admin/demo/edit-links/{seeded_data['demo_id']}/revoke/{token_doc['_id']}",
        data={"csrf_token": "edit-link-test-csrf"},
        follow_redirects=False,
    )
    assert revoked.status_code == 302
    unavailable = app.test_client().get(first_path)
    assert unavailable.status_code == 403
    assert "mitätöity" in unavailable.get_data(as_text=True).lower()

    edit_page = admin_client.get(
        f"/admin/demo/edit_demo/{seeded_data['demo_id']}"
    ).get_data(as_text=True)
    assert "Mitätöi kaikki aktiiviset muokkauslinkit" in edit_page


def test_anonymous_edit_token_can_save_with_session_csrf(app, db, seeded_data):
    client = app.test_client()
    path = f"/admin/demo/edit_demo_with_token/{seeded_data['edit_token']}"

    page = client.get(path)
    assert page.status_code == 200
    with client.session_transaction() as session:
        csrf_token = session[CSRF_SESSION_KEY]

    response = client.post(
        path,
        data={
            "csrf_token": csrf_token,
            "title": "Tokenilla päivitetty mielenosoitus",
            "date": "2026-05-01",
            "city": "Helsinki",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    updated = db.demonstrations.find_one({"_id": seeded_data["demo_id"]})
    assert updated["title"] == "Tokenilla päivitetty mielenosoitus"
    assert updated["approved"] is True
    assert seeded_data["edit_token"] not in str(list(db.super_audit_logs.find()))


def test_send_edit_link_ignores_client_url_and_does_not_use_persistent_queue(
    admin_client, monkeypatch, seeded_data
):
    import mielenosoitukset_fi.admin.admin_demo_bp as demo_routes

    sent = {}

    def capture_send_now(**kwargs):
        sent.update(kwargs)
        return True

    monkeypatch.setattr(demo_routes.email_sender, "send_now", capture_send_now)
    monkeypatch.setattr(
        demo_routes.email_sender,
        "queue_email",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("bearer link was queued")),
    )

    response = admin_client.post(
        f"/admin/demo/send_edit_link_email/{seeded_data['demo_id']}",
        json={
            "email": "recipient@example.test",
            "duration": "7d",
            "edit_link": "https://attacker.example/credential",
        },
        headers=_csrf_headers(admin_client),
    )

    assert response.status_code == 200
    assert sent["recipients"] == ["recipient@example.test"]
    assert sent["raise_on_error"] is True
    assert sent["context"]["edit_link"].startswith("http")
    assert "attacker.example" not in sent["context"]["edit_link"]


def test_recurring_editor_does_not_offer_regular_demo_edit_links(
    admin_client, seeded_data
):
    response = admin_client.get(
        f"/admin/recu_demo/edit_recu_demo/{seeded_data['recu_demo_id']}"
    )

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "generate-edit-link-btn" not in page
    assert "send_edit_link_email" not in page
    assert "duplicate-demo-btn" in page
