def test_verified_official_contact_can_cancel_demo_immediately(client, db, seeded_data):
    demo_id = seeded_data["demo_id"]
    token = seeded_data["cancel_token"]

    response = client.post(
        f"/cancel_demonstration/{token}",
        data={"reason": "Organizer confirmed cancellation."},
        follow_redirects=False,
    )

    assert response.status_code == 302

    demo = db.demonstrations.find_one({"_id": demo_id})
    assert demo["cancelled"] is True
    assert demo["cancellation_requested"] is False
    assert demo["cancelled_by"]["official_contact"] is True
    assert demo["cancelled_by"]["source"] == "organizer_link"


def test_public_report_of_cancelled_demo_creates_request_but_does_not_cancel(client, db, seeded_data):
    demo_id = seeded_data["demo_id"]

    response = client.post(
        "/report",
        data={
            "type": "demonstration",
            "demo_id": str(demo_id),
            "error": "The organizer says this demo is cancelled.",
            "mark_cancelled": "1",
            "reporter_email": "observer@example.test",
        },
        headers={"Referer": "/"},
        follow_redirects=False,
    )

    assert response.status_code == 302

    demo = db.demonstrations.find_one({"_id": demo_id})
    assert demo["cancelled"] is False
    assert demo["cancellation_requested"] is True
    assert demo["cancellation_request_source"] == "user_report"
    assert demo["cancellation_requested_by"]["official_contact"] is False
    assert demo["cancellation_requested_by"]["email"] == "observer@example.test"

    case = db.cases.find_one({"demo_id": demo_id, "type": "demo_cancellation_request"})
    assert case is not None
