def test_organization_fill_page_uses_public_org_visual_shell(client, seeded_data):
    response = client.get(f"/organization/{seeded_data['org_id']}/fill")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "org-fill-hero" in html
    assert "org-fill-layout" in html
    assert "Nykyiset tiedot" in html
    assert "Täydennä järjestön tietoja" in html
    assert "Test Organization" in html
