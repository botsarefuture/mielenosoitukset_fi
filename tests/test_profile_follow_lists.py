def test_profile_follow_counts_open_public_user_lists(user_client, db, seeded_data):
    db.users.update_one(
        {"_id": seeded_data["user_id"]},
        {"$set": {"followers": [seeded_data["friend_id"]], "following": [seeded_data["friend_id"]]}},
    )
    db.users.update_one(
        {"_id": seeded_data["friend_id"]},
        {"$set": {"followers": [seeded_data["user_id"]], "following": [seeded_data["user_id"]]}},
    )

    response = user_client.get("/users/profile/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'data-bs-target="#followersModal"' in html
    assert 'data-bs-target="#followingModal"' in html
    assert "Bob Friend" in html
    assert "@bob" in html
    assert "/users/profile/bob" in html
    assert "bob@example.test" not in html
