def test_login_does_not_redirect_back_to_notifications_api(client, seeded_data):
    response = client.post(
        "/users/auth/login?next=/api/notifications/",
        data={
            "username": seeded_data["user_username"],
            "password": "UserPass1!",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    assert "/api/notifications/" not in response.headers["Location"]


def test_login_keeps_normal_internal_page_redirect(client, seeded_data):
    response = client.post(
        "/users/auth/login?next=/users/profile/",
        data={
            "username": seeded_data["user_username"],
            "password": "UserPass1!",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/users/profile/")
