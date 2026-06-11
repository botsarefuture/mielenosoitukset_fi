def test_suggest_change_get_shows_clean_route_and_markdown_description(client, db, seeded_data):
    demo_id = seeded_data["demo_id"]
    db.demonstrations.update_one(
        {"_id": demo_id},
        {
            "$set": {
                "route": ["Keskustori", "Hameenkatu", "Sorsapuisto"],
                "description": "<p>Ensimmainen kappale.</p><p><strong>Tarkea</strong> lisatieto.</p>",
            }
        },
    )

    response = client.get(f"/suggest_change/{demo_id}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Keskustori, Hameenkatu, Sorsapuisto" in body
    assert "['Keskustori'" not in body
    assert "**Tarkea** lisatieto." in body
    assert "HTML-koodia ei tarvitse" in body
    assert "kaksoisnapsauta reittipistettä muokataksesi" in body
    assert "kaksoisnapsauttaa tagia muokataksesi" in body


def test_suggest_change_post_converts_markdown_and_normalizes_route(client, db, seeded_data):
    demo_id = seeded_data["demo_id"]

    response = client.post(
        f"/suggest_change/{demo_id}",
        data={
            "title": "Climate March Helsinki",
            "date": "2026-06-01",
            "start_time": "12:00",
            "end_time": "14:00",
            "city": "Helsinki",
            "address": "Mannerheimintie 1",
            "facebook": "",
            "route": "Keskustori\nHameenkatu\nSorsapuisto",
            "tags": "climate, peace",
            "description_markdown": "Paivitetty kuvaus.\n\n- Ensimmainen kohta\n- Toinen kohta",
            "reporter_comment": "Reitti ja kuvaus kaipaavat paivitysta.",
            "reporter_email": "editor@example.test",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    suggestion = db.demo_suggestions.find_one(
        {"demo_id": str(demo_id), "reporter_email": "editor@example.test"}
    )
    assert suggestion is not None
    assert suggestion["suggested_fields"]["route"] == ["Keskustori", "Hameenkatu", "Sorsapuisto"]
    assert suggestion["suggested_fields"]["tags"] == ["climate", "peace"]
    assert "<ul>" in suggestion["suggested_fields"]["description"]
    assert "<li>Ensimmainen kohta</li>" in suggestion["suggested_fields"]["description"]
    assert "<li>Toinen kohta</li>" in suggestion["suggested_fields"]["description"]
