def test_submit_form_exposes_default_language_selector(client):
    response = client.get("/submit")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'name="default_language"' in page
    assert "Sisällön kieli" in page
