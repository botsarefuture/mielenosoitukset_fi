def test_cities_page_renders(client):
    resp = client.get("/cities")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "Kaupunkisivut" in body
    assert "city-search-input" in body


def test_cities_page_contains_cards(client):
    resp = client.get("/cities")
    body = resp.data.decode()
    assert "city-card" in body
    assert "data-city-key" in body
