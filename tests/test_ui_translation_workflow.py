from pathlib import Path

from mielenosoitukset_fi.utils.ui_translation_catalog import proposal_key


PO_TEMPLATE = '''msgid ""
msgstr ""
"Content-Type: text/plain; charset=utf-8\\n"
"Language: {locale}\\n"

msgid "Hello world"
msgstr "{hello_translation}"

msgid "Submit demonstration"
msgstr ""
'''


def _seed_translation_catalogs(app, tmp_path: Path):
    root = tmp_path / "translations"
    app.config["TRANSLATIONS_DIR"] = str(root)

    for locale, hello_translation in [("en", "Hello world"), ("sv", "Hej världen")]:
        locale_dir = root / locale / "LC_MESSAGES"
        locale_dir.mkdir(parents=True, exist_ok=True)
        (locale_dir / "messages.po").write_text(
            PO_TEMPLATE.format(locale=locale, hello_translation=hello_translation),
            encoding="utf-8",
        )

    return root


def test_translator_can_access_ui_translation_dashboard(translator_client, app, tmp_path):
    _seed_translation_catalogs(app, tmp_path)

    response = translator_client.get("/admin/ui-translations")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Käyttöliittymäkäännökset" in body


def test_translator_can_open_ui_translation_editor(translator_client, app, tmp_path):
    _seed_translation_catalogs(app, tmp_path)

    response = translator_client.get(
        "/admin/ui-translations/en/edit?msgid=Submit%20demonstration"
    )

    assert response.status_code == 200


def test_translator_can_submit_ui_translation_proposal(translator_client, app, db, tmp_path):
    _seed_translation_catalogs(app, tmp_path)

    response = translator_client.post(
        "/admin/ui-translations/en/propose",
        data={
            "msgid": "Submit demonstration",
            "proposed_text": "Submit a demonstration",
            "notes": "Prefer imperative voice.",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    proposal = db.ui_translation_proposals.find_one(
        {"_id": proposal_key("en", "Submit demonstration")}
    )
    assert proposal["status"] == "pending"
    assert proposal["proposed_text"] == "Submit a demonstration"
    assert proposal["notes"] == "Prefer imperative voice."


def test_admin_can_approve_ui_translation_proposal(admin_client, app, db, seeded_data, tmp_path):
    root = _seed_translation_catalogs(app, tmp_path)
    db.ui_translation_proposals.insert_one(
        {
            "_id": proposal_key("en", "Submit demonstration"),
            "locale": "en",
            "msgid": "Submit demonstration",
            "current_msgstr": "",
            "proposed_text": "Submit a demonstration",
            "status": "pending",
            "submitted_by": str(seeded_data["translator_id"]),
            "submitted_by_name": "Translator User",
        }
    )

    response = admin_client.post(
        "/admin/ui-translations/en/approve",
        data={
            "msgid": "Submit demonstration",
            "review_notes": "Looks good.",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    po_contents = (root / "en" / "LC_MESSAGES" / "messages.po").read_text(encoding="utf-8")
    assert 'msgid "Submit demonstration"' in po_contents
    assert 'msgstr "Submit a demonstration"' in po_contents
    assert (root / "en" / "LC_MESSAGES" / "messages.mo").exists()

    proposal = db.ui_translation_proposals.find_one(
        {"_id": proposal_key("en", "Submit demonstration")}
    )
    assert proposal["status"] == "approved"
    assert proposal["review_notes"] == "Looks good."
