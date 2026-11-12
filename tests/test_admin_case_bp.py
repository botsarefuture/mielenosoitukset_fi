from mielenosoitukset_fi.scripts.auto_close_cases import _resolve as resolve_auto_close_cases


def test_accept_demo_closes_linked_support_case(admin_client, db, seeded_data):
    response = admin_client.post(
        f"/admin/demo/accept_demo/{seeded_data['pending_demo_id']}",
        json={},
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200

    case = db.cases.find_one({"_id": seeded_data["case_id"]})
    assert case["meta"]["closed"] is True
    assert case["meta"]["closed_reason"] == "demo_approved"
    assert any(log.get("action_type") == "approve_demo" for log in case["action_logs"])


def test_case_pages_render_clean_support_case_views(admin_client, seeded_data):
    list_response = admin_client.get("/admin/case/")
    detail_response = admin_client.get(f"/admin/case/{seeded_data['case_id']}/")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200

    list_page = list_response.get_data(as_text=True)
    detail_page = detail_response.get_data(as_text=True)

    assert "Tapaukset & eskaloinnit" in list_page
    assert "Pending Demonstration" in detail_page
    assert "Sisaiset muistiinpanot" in detail_page


def test_approve_demo_token_closes_linked_support_case(client, db, seeded_data):
    response = client.post(
        f"/admin/demo/approve_demo_with_token/{seeded_data['approve_token']}",
        follow_redirects=False,
    )

    assert response.status_code == 302

    case = db.cases.find_one({"_id": seeded_data["case_id"]})
    assert case["meta"]["closed"] is True
    assert case["meta"]["closed_reason"] == "demo_approved"
    assert any(log.get("action_type") == "approve_demo" for log in case["action_logs"])


def test_reject_demo_token_closes_linked_support_case(client, db, seeded_data):
    response = client.post(
        f"/admin/demo/reject_demo_with_token/{seeded_data['reject_token']}",
        follow_redirects=False,
    )

    assert response.status_code == 302

    case = db.cases.find_one({"_id": seeded_data["case_id"]})
    assert case["meta"]["closed"] is True
    assert case["meta"]["closed_reason"] == "demo_rejected"
    assert any(log.get("action_type") == "reject_demo" for log in case["action_logs"])


def test_deescalate_writes_case_history(admin_client, db, seeded_data):
    db.cases.update_one(
        {"_id": seeded_data["case_id"]},
        {"$set": {"meta.superior_needed": True}},
    )

    response = admin_client.post(f"/admin/case/{seeded_data['case_id']}/deescalate")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True

    case = db.cases.find_one({"_id": seeded_data["case_id"]})
    assert case["meta"]["superior_needed"] is False
    assert "history" not in case
    assert case["case_history"][-1]["action"] == "Eskalointi poistettu"


def test_auto_close_cases_respects_approved_field(db, seeded_data):
    db.demonstrations.update_one(
        {"_id": seeded_data["pending_demo_id"]},
        {"$set": {"approved": True, "rejected": False, "cancelled": False}},
    )

    checked, closed = resolve_auto_close_cases(db)

    assert checked >= 1
    assert closed == 1

    case = db.cases.find_one({"_id": seeded_data["case_id"]})
    assert case["meta"]["closed"] is True
    assert case["meta"]["closed_reason"] == "Demo hyväksytty"
