def test_public_guides_are_accessible_without_login(client):
    response = client.get("/ohjeet")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Selkeät ohjeet kaikille järjestäjille" in body
    assert "Ohjekeskus" in body
    assert "Jos ilmoituksen lähetys ei mene heti läpi" in body
    assert "yritä tarvittaessa uudelleen" in body


def test_submit_page_links_to_guides_for_submission_help(client):
    response = client.get("/submit")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'href="/ohjeet#submit-help"' in body or 'href="/ohjeet/#submit-help"' in body
    assert "Jos lähetys takkuaa, katso ohjeet" in body
