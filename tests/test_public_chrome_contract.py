from pathlib import Path

import pytest
from babel.messages import pofile


BASE = Path("mielenosoitukset_fi/templates/base.html")
API_DOCS = Path("mielenosoitukset_fi/templates/api_docs.html")
WORKSPACE = Path("mielenosoitukset_fi/static/css/user-workspace.css")


def test_api_docs_uses_shared_page_chrome_without_template_css():
    source = API_DOCS.read_text(encoding="utf-8")

    assert '<header class="public-page-header">' in source
    assert 'class="public-page-header__content"' in source
    assert 'class="public-page-header__title"' in source
    assert 'class="public-page-header__meta api-docs-meta"' in source
    assert "<style" not in source
    assert "--api-docs-" not in source


def test_public_footer_has_one_semantic_shared_structure():
    source = BASE.read_text(encoding="utf-8")

    assert '<footer class="footer public-site-footer">' in source
    assert 'class="public-site-footer__brand"' in source
    assert 'class="footer-links public-site-footer__links"' in source
    assert 'class="social-media-links public-site-footer__social"' in source
    assert 'class="footer-links auth-buttons public-site-footer__auth"' in source
    assert 'class="footer-separator"' not in source
    assert 'style="color: var(--secondary_color);"' not in source


def test_public_chrome_css_uses_product_tokens_and_namespaced_components():
    source = WORKSPACE.read_text(encoding="utf-8")

    for selector in (
        ".public-page-header",
        ".public-page-header__content",
        ".public-site-footer",
        ".api-docs-layout",
        ".api-docs-sidebar",
    ):
        assert selector in source

    section = source.split("PUBLIC PAGE CHROME", 1)[1].split("BUTTONS", 1)[0]
    assert "var(--product-" in section
    assert "--api-docs-" not in section
    assert "var(--admin-" not in section


@pytest.mark.parametrize(
    ("locale", "expected"),
    [
        (
            "en",
            {
                "API-dokumentaatio": "API documentation",
                "Ihmisluettava dokumentaatio julkiselle API:lle.": "Human-readable documentation for the public API.",
                "Sivuston alatunniste": "Site footer",
            },
        ),
        (
            "sv",
            {
                "API-dokumentaatio": "API-dokumentation",
                "Ihmisluettava dokumentaatio julkiselle API:lle.": "Läsbar dokumentation för det offentliga API:et.",
                "Sivuston alatunniste": "Sidfot",
            },
        ),
    ],
)
def test_public_chrome_labels_are_translated(locale, expected):
    path = Path(f"mielenosoitukset_fi/translations/{locale}/LC_MESSAGES/messages.po")
    with path.open("r", encoding="utf-8") as catalog_file:
        catalog = pofile.read_po(catalog_file)

    for message_id, translation in expected.items():
        assert catalog.get(message_id).string == translation


@pytest.mark.e2e
@pytest.mark.integration
def test_api_docs_chrome_is_theme_aware_and_portrait_safe(live_server, browser_page):
    browser_page.add_init_script("localStorage.setItem('theme', 'light')")
    browser_page.goto(f"{live_server}/api-docs/", wait_until="domcontentloaded")

    header = browser_page.locator(".public-page-header")
    footer = browser_page.locator(".public-site-footer")
    assert header.is_visible()
    assert footer.is_visible()
    light_background = header.evaluate("node => getComputedStyle(node).backgroundImage")
    assert light_background != "none"

    browser_page.locator(".theme-toggle").click()
    assert "dark" in (browser_page.locator("html").get_attribute("class") or "")
    assert header.is_visible()
    assert footer.is_visible()

    browser_page.set_viewport_size({"width": 360, "height": 800})
    assert browser_page.locator(".api-docs-sidebar").is_visible()
    assert browser_page.locator(".public-page-header__meta").is_visible()
    overflow = browser_page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 1
