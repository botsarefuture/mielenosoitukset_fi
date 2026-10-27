import json
from pathlib import Path

import pytest
from babel.messages import pofile


TAG_TEMPLATE = Path("mielenosoitukset_fi/templates/tag_list.html")

TAG_LABELS = {
    "Poista suodattimet",
    "Ilmoita uusi mielenosoitus",
    "Ei löytynyt mielenosoituksia näillä hakukriteereillä. Kokeile poistaa suodattimia tai hae uudelleen.",
    "Tällä tagilla ei ole näkyvillä olevia mielenosoituksia.",
}


def test_tag_list_uses_localized_stable_empty_state_markup():
    source = Path('mielenosoitukset_fi/templates/_layouts/demonstration-list.html').read_text()
    page = Path('frontend/src/pages/DemonstrationListingPage.tsx').read_text()
    controller = Path('frontend/src/components/listings/controller.tsx').read_text()
    assert 'id="clear-filters-btn"' in page
    assert 'clear.hidden = !filtered' in controller
    assert 'range.count > 0' in controller
    assert 'clearFilters' in controller
    assert 'innerHTML' not in controller
    for label in TAG_LABELS:
        assert f"_('{label}')" in source


def test_tag_list_labels_have_english_and_swedish_translations():
    for locale in ("en", "sv"):
        catalog_path = Path(
            f"mielenosoitukset_fi/translations/{locale}/LC_MESSAGES/messages.po"
        )
        with catalog_path.open(encoding="utf-8") as catalog_file:
            catalog = pofile.read_po(catalog_file)

        for label in TAG_LABELS:
            message = catalog.get(label)
            assert message is not None, (locale, label)
            assert message.string, (locale, label)


@pytest.mark.parametrize(
    ("locale", "filtered_empty", "tag_empty", "clear_filters", "submit_label"),
    [
        (
            "en",
            "No demonstrations matched these filters. Clear some filters or try another search.",
            "There are no visible demonstrations with this tag.",
            "Clear filters",
            "Submit a new demonstration",
        ),
        (
            "sv",
            "Inga demonstrationer matchade dessa filter. Ta bort några filter eller gör en ny sökning.",
            "Det finns inga synliga demonstrationer med denna tagg.",
            "Rensa filter",
            "Anmäl en ny demonstration",
        ),
    ],
)
def test_tag_route_renders_localized_empty_state_contract(
    app,
    client,
    locale,
    filtered_empty,
    tag_empty,
    clear_filters,
    submit_label,
):
    app.config["BABEL_PUBLIC_LOCALES"] = ["fi", "en", "sv"]
    with client.session_transaction() as session:
        session["locale"] = locale

    response = client.get("/tag/climate")

    assert response.status_code == 200
    import re
    body = response.get_data(as_text=True)
    match = re.search(r'<script id="demonstration-listing-props" type="application/json">(.*?)</script>', body, re.S)
    messages = json.loads(match.group(1))['messages']
    assert messages['filteredEmpty'] == filtered_empty
    assert messages['empty'] == tag_empty
    assert messages['clearFilters'] == clear_filters
    assert messages['submitEvent'] == submit_label
