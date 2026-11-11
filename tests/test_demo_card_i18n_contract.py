from pathlib import Path

import pytest
from babel.messages import pofile


CARD_LABELS = {
    "Ladataan mielenosoituksia...",
    "Lataa lisää",
    "Peruttu",
    "Tänään",
    "alkaen",
    "Kirjaudu sisään käyttääksesi sosiaalisia toimintoja",
    "osallistuu",
    "Ladataan kavereita...",
    "Kutsu kavereita",
}


def test_demo_card_labels_have_english_and_swedish_translations():
    for locale in ("en", "sv"):
        catalog_path = Path(
            f"mielenosoitukset_fi/translations/{locale}/LC_MESSAGES/messages.po"
        )
        with catalog_path.open(encoding="utf-8") as catalog_file:
            catalog = pofile.read_po(catalog_file)

        for label in CARD_LABELS:
            message = catalog.get(label)
            assert message is not None, (locale, label)
            assert message.string, (locale, label)


@pytest.mark.parametrize(
    ("locale", "expected"),
    [
        (
            "en",
            {
                'window.currentLocale = "en";',
                'loading: "Loading demonstrations..."',
                'cancelled: "Cancelled"',
                '<span>Loading friends...</span>',
                '<span class="invite-text">Invite friends</span>',
            },
        ),
        (
            "sv",
            {
                'window.currentLocale = "sv";',
                'loading: "Laddar demonstrationer..."',
                'cancelled: "Inst\\u00e4lld"',
                '<span>Laddar v\u00e4nner...</span>',
                '<span class="invite-text">Bjud in v\u00e4nner</span>',
            },
        ),
    ],
)
def test_demo_list_renders_shared_card_contract_for_active_locale(
    app, client, locale, expected
):
    app.config["BABEL_PUBLIC_LOCALES"] = ["fi", "en", "sv"]
    with client.session_transaction() as session:
        session["locale"] = locale

    response = client.get("/demonstrations")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    import json, re
    match = re.search(r'<script id="demonstration-listing-props" type="application/json">(.*?)</script>', body, re.S)
    props = json.loads(match.group(1))
    assert props['locale'] == locale
    with app.test_request_context():
        from flask import session
        from flask_babel import gettext
        session['locale'] = locale
        for key, label in {'loading': 'Ladataan mielenosoituksia...', 'cancelled': 'Peruttu',
                           'loadingFriends': 'Ladataan kavereita...', 'invite': 'Kutsu kavereita'}.items():
            assert props['messages'][key] == gettext(label)
