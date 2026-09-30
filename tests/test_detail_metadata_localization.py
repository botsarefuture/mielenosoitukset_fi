import html
import json
import re
from pathlib import Path

import pytest
from babel.messages import pofile


DETAIL_TEMPLATE = Path("mielenosoitukset_fi/templates/detail.html")

METADATA_LABELS = {
    "Mielenosoitus",
    "Mielenosoituksen tiedot.",
    "Tuntematon osoite",
    "Tuntematon kirjoittaja",
    "mielenosoitus",
    "tapahtuma",
    "%(title)s – mielenosoitus kaupungissa %(city)s",
}


def _meta_values(body, attribute, key):
    pattern = (
        rf'<meta\s+{attribute}="{re.escape(key)}"\s+'
        rf'content="([^"]*)"\s*/?>'
    )
    return [html.unescape(value).strip() for value in re.findall(pattern, body)]


def test_detail_metadata_uses_one_localized_safe_contract():
    source = DETAIL_TEMPLATE.read_text(encoding="utf-8")

    assert "demo.get('title', 'Mielenosoitus')" not in source
    assert "demo.get('description', 'Mielenosoituksen tiedot.')" not in source
    assert "demo.get('address', 'Tuntematon osoite')" not in source
    assert "<!-- Social / Card Meta" not in source
    assert '"name": {{ metadata_title | tojson }}' in source
    assert '"description": {{ metadata_description | tojson }}' in source
    assert '"latitude": {{ (demo.get(\'latitude\') or \'\') | tojson }}' in source


def test_detail_metadata_labels_have_english_and_swedish_translations():
    for locale in ("en", "sv"):
        catalog_path = Path(
            f"mielenosoitukset_fi/translations/{locale}/LC_MESSAGES/messages.po"
        )
        with catalog_path.open(encoding="utf-8") as catalog_file:
            catalog = pofile.read_po(catalog_file)

        for label in METADATA_LABELS:
            message = catalog.get(label)
            assert message is not None, (locale, label)
            assert message.string, (locale, label)


@pytest.mark.parametrize(
    ("locale", "expected"),
    [
        (
            "en",
            {
                "title": "Climate March Helsinki",
                "city": "Helsinki",
                "summary": "Climate March Helsinki – demonstration in Helsinki",
                "description": "Demonstration details.",
                "address": "Mannerheimintie 1, Helsinki",
                "author": "Verified Test Organization",
                "section": "Events",
                "tags": ["demonstration", "event"],
            },
        ),
        (
            "sv",
            {
                "title": "Climate March Helsinki",
                "city": "Helsinki",
                "summary": "Climate March Helsinki – demonstration i Helsinki",
                "description": "Demonstrationsuppgifter.",
                "address": "Mannerheimintie 1, Helsinki",
                "author": "Verified Test Organization",
                "section": "Evenemang",
                "tags": ["demonstration", "evenemang"],
            },
        ),
    ],
)
def test_detail_route_localizes_empty_metadata_and_emits_one_twitter_set(
    app, client, db, seeded_data, locale, expected
):
    app.config["BABEL_PUBLIC_LOCALES"] = ["fi", "en", "sv"]
    db.demonstrations.update_one(
        {"_id": seeded_data["demo_id"]},
        {
            "$set": {
                "description": "",
                "section": "",
                "tags": [],
                "translations": {},
                "approved": True,
                "hide": False,
            }
        },
    )
    with client.session_transaction() as session:
        session["locale"] = locale

    response = client.get(
        f"/demonstration/{seeded_data['demo_id']}?metadata-test=1"
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)

    title_match = re.search(r"<title>\s*(.*?)\s*</title>", body, re.DOTALL)
    assert title_match
    assert html.unescape(title_match.group(1)).strip().startswith(expected["title"])

    og_title = _meta_values(body, "property", "og:title")
    assert len(og_title) == 1
    assert og_title[0].startswith(expected["title"])
    assert _meta_values(body, "property", "og:description")[0].startswith(
        expected["summary"]
    )
    assert _meta_values(body, "property", "og:event:location") == [
        f'{expected["address"]}, {expected["city"]}'
    ]
    assert _meta_values(body, "property", "article:author") == [expected["author"]]
    assert _meta_values(body, "property", "article:section") == [
        expected["section"]
    ]
    assert _meta_values(body, "property", "article:tag") == expected["tags"]

    assert len(_meta_values(body, "name", "twitter:card")) == 1
    assert len(_meta_values(body, "name", "twitter:title")) == 1
    assert _meta_values(body, "name", "twitter:description") == [
        expected["description"]
    ]
    assert len(_meta_values(body, "name", "twitter:image")) == 1

    json_ld_match = re.search(
        r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
        body,
        re.DOTALL,
    )
    assert json_ld_match
    structured_data = json.loads(json_ld_match.group(1))
    assert structured_data["name"] == expected["title"]
    assert structured_data["description"] == expected["description"]
    assert structured_data["location"]["name"] == expected["address"]
    assert structured_data["organizer"]["name"] == expected["author"]
