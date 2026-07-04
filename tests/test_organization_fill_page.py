def test_organization_fill_page_uses_public_org_visual_shell(client, seeded_data):
    response = client.get(f"/organization/{seeded_data['org_id']}/fill")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "org-fill-hero" in html
    assert "org-fill-layout" in html
    assert "Nykyiset tiedot" in html
    assert "Täydennä järjestön tietoja" in html
    assert 'name="logo"' in html
    assert "Test Organization" in html


def test_organization_fill_submission_stores_logo_suggestion(client, db, seeded_data):
    logo_url = "https://example.test/logo.png"

    response = client.post(
        f"/organization/{seeded_data['org_id']}/save_suggestion",
        data={
            "name": "Test Organization",
            "description": "Updated description",
            "website": "https://example.test/org",
            "email": "contact@test-org.example",
            "logo": logo_url,
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    suggestion = db.org_edit_suggestions.find_one(
        {"organization_id": seeded_data["org_id"], "fields.logo": logo_url}
    )
    assert suggestion is not None
    assert suggestion["fields"]["logo"] == logo_url


def test_admin_can_apply_logo_suggestion(admin_client, db, seeded_data):
    logo_url = "https://example.test/new-logo.png"
    suggestion = db.org_edit_suggestions.find_one({"_id": seeded_data["org_suggestion_id"]})
    db.org_edit_suggestions.update_one(
        {"_id": suggestion["_id"]},
        {"$set": {"fields.logo": logo_url}},
    )

    response = admin_client.post(
        f"/admin/organization/{seeded_data['org_id']}/suggestion/{suggestion['_id']}/apply",
        data={"apply_fields": ["logo"]},
        follow_redirects=False,
    )

    assert response.status_code == 302
    organization = db.organizations.find_one({"_id": seeded_data["org_id"]})
    assert organization["logo"] == logo_url
