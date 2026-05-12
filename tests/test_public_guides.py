def test_public_guides_are_accessible_without_login(client):
    response = client.get("/ohjeet")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Selkeät ohjeet kaikille järjestäjille" in body
    assert "Ohjekeskus" in body
