from pathlib import Path

import pytest
from babel.messages import pofile


TEMPLATES = Path("mielenosoitukset_fi/templates")
CARD_PARTIAL = TEMPLATES / "_modals/_demo-card-template.html"
RENDERER = Path("mielenosoitukset_fi/static/js/demo-card-render.js")

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


def _template_sources():
    return {
        path: path.read_text(encoding="utf-8")
        for path in TEMPLATES.rglob("*.html")
    }


def test_every_dynamic_demo_card_consumer_includes_shared_card_contract():
    sources = _template_sources()
    consumers = {
        path: source
        for path, source in sources.items()
        if "js/demo-card-render.js" in source
    }

    assert consumers
    for path, source in consumers.items():
        assert "_modals/_demo-card-template.html" in source, path


def test_demo_card_i18n_is_owned_only_by_the_shared_card_partial():
    sources = _template_sources()
    owners = {
        path.relative_to(TEMPLATES)
        for path, source in sources.items()
        if "window.demoCardI18n =" in source
    }

    assert owners == {Path("_modals/_demo-card-template.html")}

    partial = CARD_PARTIAL.read_text(encoding="utf-8")
    assert "window.currentLocale =" in partial
    assert "Object.freeze" in partial
    for key in (
        "loading",
        "loadMore",
        "cancelled",
        "today",
        "startingFrom",
        "loginPrompt",
        "attendingSuffix",
    ):
        assert f"{key}:" in partial

    for label in CARD_LABELS:
        assert f"_('{label}')" in partial


def test_demo_card_renderer_has_no_finnish_runtime_fallbacks():
    source = RENDERER.read_text(encoding="utf-8")

    for label in (
        "Ladataan mielenosoituksia...",
        "Lataa lisää",
        "Peruttu",
        "Tänään",
        "alkaen",
        "Kirjaudu sisään käyttääksesi sosiaalisia toimintoja",
        "osallistuu",
    ):
        assert label not in source


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
    for fragment in expected:
        assert fragment in body
