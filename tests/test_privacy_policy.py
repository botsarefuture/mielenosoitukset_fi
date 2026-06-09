def test_privacy_policy_discloses_current_personal_data_processing(client):
    response = client.get("/privacy")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Rekisterinpitäjä ja yhteystiedot" in page
    assert "Hallinta-, muutos- ja virhelokit" in page
    assert "Katseluanalytiikka" in page
    assert "Kaikille nykyisille lokikokoelmille ei ole vielä toteutettu" in page
    assert "Tietosuojavaltuutetun toimiston" in page
