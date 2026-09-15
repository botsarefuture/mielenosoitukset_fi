from datetime import date, timedelta


def test_public_demonstrations_list_uses_summary_payload(client, db, seeded_data):
    future_date = (date.today() + timedelta(days=7)).isoformat()
    db.demonstrations.update_one(
        {"_id": seeded_data["demo_id"]},
        {
            "$set": {
                "date": future_date,
                "large_internal_payload": "x" * 10000,
                "edit_history": [{"field": "title", "old": "A", "new": "B"}],
                "private_notes": "Not needed for the public list endpoint.",
            }
        },
    )

    response = client.get(
        "/api/demonstrations",
        query_string={"max_days_till": "60", "include_cancelled": "true"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["results"]

    demo = next(item for item in payload["results"] if item["_id"] == str(seeded_data["demo_id"]))
    assert demo["title"] == "Climate March Helsinki"
    assert demo["date"] == future_date
    assert demo["city"] == "Helsinki"
    assert demo["address"] == "Mannerheimintie 1, Helsinki"
    assert demo["cover_picture"] == "https://cdn.example.test/covers/demo.jpg"
    assert demo["preview_image"] == "https://cdn.example.test/previews/demo.jpg"
    assert demo["latitude"] == "60.1699"
    assert demo["longitude"] == "24.9384"

    assert "large_internal_payload" not in demo
    assert "edit_history" not in demo
    assert "private_notes" not in demo
