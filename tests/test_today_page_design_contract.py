from pathlib import Path

import pytest


TEMPLATE = Path("mielenosoitukset_fi/templates/today_demos.html")
CSS = Path("mielenosoitukset_fi/static/css/today-demos.css")


def test_today_page_uses_shared_header_and_scoped_stylesheet():
    source = TEMPLATE.read_text(encoding="utf-8")

    assert '<header class="public-page-header">' in source
    assert 'class="public-page-header__content"' in source
    assert 'class="public-page-header__title"' in source
    assert 'class="public-page-header__description"' in source
    assert 'class="public-page-header__meta today-actions"' in source
    assert "20260930-today-demos-2" in source
    assert "<style" not in source
    assert "style=" not in source
    assert "<main" not in source


def test_today_component_uses_product_tokens_for_all_states():
    css = CSS.read_text(encoding="utf-8")

    for selector in (
        ".today-demo",
        ".today-tag",
        ".today-empty",
        ".today-demo:focus-visible",
        "@media (max-width: 42.5rem)",
        "@media (prefers-reduced-motion: reduce)",
    ):
        assert selector in css
    assert "var(--product-surface)" in css
    assert "var(--product-text)" in css
    assert "var(--product-success-soft)" in css
    assert "--color-" not in css
    assert "--admin-workspace-" not in css
    assert "#ffffff" not in css


def test_empty_state_secondary_action_outweighs_shared_button_rules():
    """`base.html` loads `user-workspace.css` after this page stylesheet.

    The shared ``.button`` and ``.button:hover`` rules therefore win any tie on
    source order, so the empty state's secondary action has to be scoped to its
    container (0-2-0 / 0-3-0) to keep its outlined treatment instead of silently
    rendering as a second primary action.
    """
    css = CSS.read_text(encoding="utf-8")

    assert "\n.today-action--outline" not in css
    assert ".today-empty__actions .today-action--outline {" in css
    assert ".today-empty__actions .today-action--outline:hover {" in css

    scoped = css.index(".today-empty__actions .today-action--outline {")
    assert "var(--product-surface-muted)" in css[scoped:css.index("}", scoped)]


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize(
    ("theme", "viewport"),
    [
        ("light", {"width": 1440, "height": 900}),
        ("dark", {"width": 360, "height": 800}),
    ],
)
def test_today_page_is_theme_aware_and_portrait_safe(
    live_server, browser_page, theme, viewport
):
    browser_page.set_viewport_size(viewport)
    browser_page.add_init_script(f"localStorage.setItem('theme', '{theme}')")
    browser_page.goto(
        f"{live_server}/mielenosoitukset-tanaan",
        wait_until="domcontentloaded",
    )

    assert browser_page.locator(".public-page-header").is_visible()
    assert browser_page.locator(".today-content").is_visible()
    assert theme in (browser_page.locator("html").get_attribute("class") or "")
    assert browser_page.evaluate(
        "document.documentElement.scrollWidth <= window.innerWidth + 1"
    )
