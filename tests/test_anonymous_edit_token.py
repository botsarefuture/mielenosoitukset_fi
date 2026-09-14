def test_anonymous_edit_token_renders_without_city_admin_navigation(app, seeded_data):
    client = app.test_client()

    response = client.get(
        f"/admin/demo/edit_demo_with_token/{seeded_data['edit_token']}"
    )

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Kaupunkiadminin näkymä" not in page
    assert "demo-form" in page
