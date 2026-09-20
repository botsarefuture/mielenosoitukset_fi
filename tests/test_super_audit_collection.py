from datetime import datetime


def test_super_audit_collection_paginates_with_stable_filter_state(admin_client, db):
    timestamp = datetime.utcnow()
    db.super_audit_logs.insert_many(
        [
            {
                "timestamp": timestamp,
                "event": "test_audit_event",
                "request": {
                    "method": "POST",
                    "path": f"/admin/test/{index:02d}",
                    "remote_addr": "127.0.0.1",
                },
                "payload": {"marker": f"Audit marker {index:02d}"},
            }
            for index in range(45)
        ]
    )

    first = admin_client.get(
        "/admin/demo/super_audit/logs?event=test_audit_event&page=1&per_page=20"
    )
    second = admin_client.get(
        "/admin/demo/super_audit/logs?event=test_audit_event&page=2&per_page=20"
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_page = first.get_data(as_text=True)
    second_page = second.get_data(as_text=True)
    assert "Audit marker 44" in first_page
    assert "Audit marker 25" in first_page
    assert "Audit marker 24" not in first_page
    assert "Audit marker 25" not in second_page
    assert "Audit marker 24" in second_page
    assert "Audit marker 05" in second_page
    assert "Näytetään 21–40 / 45 tapahtumasta" in second_page
    assert "event=test_audit_event" in second_page
    assert "per_page=20" in second_page


def test_super_audit_collection_uses_shared_empty_state(admin_client):
    response = admin_client.get(
        "/admin/demo/super_audit/logs?event=event-that-does-not-exist"
    )

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Tapahtumia ei löytynyt" in page
    assert "admin-empty-state__title" in page
