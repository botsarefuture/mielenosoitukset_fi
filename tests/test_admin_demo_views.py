def test_create_demo_hides_edit_only_controls(admin_client):
    response = admin_client.get("/admin/demo/create_demo")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'name="cover_picture"' in page
    assert "Luo muokkauslinkki" not in page
    assert "Luo kopio mielenosoituksesta" not in page


def test_edit_demo_shows_edit_only_controls(admin_client, seeded_data):
    response = admin_client.get(f"/admin/demo/edit_demo/{seeded_data['demo_id']}")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Luo muokkauslinkki" in page
    assert "Luo kopio mielenosoituksesta" in page
