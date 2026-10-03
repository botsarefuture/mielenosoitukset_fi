"""Contract coverage for the shared, localized terms page."""

import re
from pathlib import Path

import pytest
from babel.messages import pofile


TERMS = Path("mielenosoitukset_fi/templates/terms.html")
WORKSPACE = Path("mielenosoitukset_fi/static/css/user-workspace.css")
BASE = Path("mielenosoitukset_fi/templates/base.html")


def _set_locale(client, locale):
    with client.session_transaction() as session:
        session["locale"] = locale


def test_terms_uses_shared_semantic_page_contract_without_local_styles():
    source = TERMS.read_text(encoding="utf-8")

    assert '{% extends "base.html" %}' in source
    assert "<!DOCTYPE" not in source
    assert "<html" not in source
    assert "<head>" not in source
    assert "<body>" not in source
    assert "<style" not in source
    assert "style=" not in source
    assert '<header class="public-page-header">' in source
    assert 'class="public-page-header__content"' in source
    assert 'class="public-page-header__title" id="terms-title"' in source
    assert source.count('class="public-prose-card"') == 4
    assert '<time datetime="2025-10-12">' in source
    assert 'href="mailto:hallinto@mielenosoitukset.fi"' in source


def test_terms_shared_prose_component_uses_product_tokens_and_focus_state():
    css = WORKSPACE.read_text(encoding="utf-8")

    for selector in (
        ".public-content-stack",
        ".public-prose-card",
        ".public-prose-card h2",
        ".public-prose-card a:focus-visible",
    ):
        assert selector in css
    prose_section = css.split(".public-content-stack", 1)[1].split(
        ".api-docs-wrap", 1
    )[0]
    assert "var(--product-surface)" in prose_section
    assert "var(--product-border)" in prose_section
    assert "var(--product-text)" in prose_section
    assert "--admin-workspace-" not in prose_section
    assert re.search(
        r"css/user-workspace\.css.*v='\d{8}-user-workspace-\d+'",
        BASE.read_text(encoding="utf-8"),
    )


@pytest.mark.parametrize(
    ("locale", "expected_title", "expected_heading"),
    [
        ("fi", "Käyttöehdot", "Valitusprosessi"),
        ("en", "Terms of use", "Appeals process"),
        ("sv", "Användarvillkor", "Överklagandeprocess"),
    ],
)
def test_terms_route_follows_active_locale(
    app, client, seeded_data, locale, expected_title, expected_heading
):
    app.config["BABEL_PUBLIC_LOCALES"] = ["fi", "en", "sv"]
    _set_locale(client, locale)

    response = client.get("/terms")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert f'id="terms-title">{expected_title}</h1>' in body
    assert f'id="terms-appeal">{expected_heading}</h2>' in body
    assert '<html lang="fi"' in body if locale == "fi" else f'<html lang="{locale}"' in body


@pytest.mark.parametrize("locale", ["en", "sv"])
def test_terms_catalog_has_complete_nonempty_translations(locale):
    source = TERMS.read_text(encoding="utf-8")
    catalog_path = Path(
        f"mielenosoitukset_fi/translations/{locale}/LC_MESSAGES/messages.po"
    )
    with catalog_path.open("r", encoding="utf-8") as catalog_file:
        catalog = pofile.read_po(catalog_file)

    for expected in (
        "Käyttöehdot",
        "Yleiset ehdot",
        "Valitusprosessi",
        "Vastuunrajoitus",
        "Muutokset käyttöehtoihin",
        "Käyttämällä sivustoamme hyväksyt nämä ehdot.",
    ):
        message = catalog.get(expected)
        assert message is not None
        assert message.string
        assert expected in source


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize(
    ("theme", "viewport"),
    [
        ("light", {"width": 1440, "height": 900}),
        ("dark", {"width": 360, "height": 800}),
    ],
)
def test_terms_is_theme_aware_and_portrait_safe(
    app, live_server, browser_page, theme, viewport
):
    app.config["BABEL_PUBLIC_LOCALES"] = ["fi", "en", "sv"]
    browser_page.set_viewport_size(viewport)
    browser_page.add_init_script(
        f"localStorage.setItem('theme', '{theme}')"
    )
    browser_page.goto(f"{live_server}/terms", wait_until="domcontentloaded")

    assert browser_page.locator("#terms-title").is_visible()
    assert browser_page.locator(".public-prose-card").count() == 4
    assert browser_page.locator(".public-prose-card").first.is_visible()
    assert browser_page.evaluate(
        "document.documentElement.scrollWidth <= window.innerWidth + 1"
    )
    assert theme in (browser_page.locator("html").get_attribute("class") or "")
