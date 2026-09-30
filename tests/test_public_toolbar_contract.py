"""Contract checks for the contextual toolbox on public pages."""

import json
from pathlib import Path

import pytest


TEMPLATE_PATH = Path("mielenosoitukset_fi/templates/toolbar.html")
STYLESHEET_PATH = Path("mielenosoitukset_fi/static/css/toolbox.css")
INLINE_STYLE_BASELINE = Path("tests/public_inline_style_baseline.json")


def _template_source():
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def _stylesheet_source():
    return STYLESHEET_PATH.read_text(encoding="utf-8")


def test_toolbar_uses_shared_accessible_confirmation_dialog():
    source = _template_source()

    assert "<style" not in source
    assert "confirm(" not in source
    assert 'id="toolbarConfirmModal"' in source
    assert 'aria-labelledby="toolbarConfirmTitle"' in source
    assert 'aria-describedby="toolbar-confirm-message"' in source
    assert "bootstrap.Modal.getOrCreateInstance" in source
    assert "shown.bs.modal" in source
    assert "hidden.bs.modal" in source
    assert "returnFocus.focus()" in source


def test_toolbar_renders_api_values_without_html_interpolation():
    source = _template_source()

    assert ".innerHTML" not in source
    assert "replaceChildren(" in source
    assert "document.createElement('p')" in source
    assert "document.createTextNode" in source
    assert "toolbarConfirmMessage.textContent" in source


def test_toolbar_collapse_control_exposes_state_and_relationship():
    source = _template_source()

    assert 'aria-controls="public-toolbox-actions"' in source
    assert 'aria-expanded="false"' in source
    assert 'id="public-toolbox-actions" hidden' in source
    assert "body.hidden = collapsed" in source
    assert "toggle.setAttribute('aria-expanded', String(!collapsed))" in source
    assert "data-collapse-label" in source
    assert "data-expand-label" in source


def test_toolbar_styles_are_scoped_and_use_product_tokens():
    source = _stylesheet_source()

    assert ".public-toolbox" in source
    assert ".public-toolbox__header" in source
    assert ".public-toolbox__body[hidden]" in source
    assert "@media (max-width: 35rem)" in source
    assert "focus-visible" in source
    assert "--admin-workspace-" not in source
    assert "var(--product-surface)" in source
    assert "var(--product-text)" in source
    assert "var(--product-border)" in source
    assert "var(--product-action-bg)" in source


def test_toolbar_inline_style_debt_was_removed_from_baseline():
    baseline = json.loads(INLINE_STYLE_BASELINE.read_text(encoding="utf-8"))

    assert "toolbar.html" not in baseline["style_blocks"]


def test_toolbar_stylesheet_cache_key_is_versioned():
    source = _template_source()

    assert "20260930-public-toolbox-1" in source


def test_toolbar_renders_for_authenticated_admin_demo_context(
    admin_client, seeded_data
):
    response = admin_client.get(
        f"/demonstration/{seeded_data['demo_id']}?force_reload=1"
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'id="toolbox-sidebar"' in body
    assert 'id="toolbarConfirmModal"' in body
    assert 'aria-controls="public-toolbox-actions"' in body


def test_toolbar_is_omitted_without_demo_or_organization_context(admin_client):
    response = admin_client.get("/")

    assert response.status_code == 200
    assert 'id="toolbox-sidebar"' not in response.get_data(as_text=True)


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize(
    ("theme", "viewport"),
    [
        ("light", {"width": 1440, "height": 900}),
        ("dark", {"width": 390, "height": 844}),
    ],
)
def test_toolbar_fits_public_detail_in_both_themes(
    admin_client,
    seeded_data,
    live_server,
    browser_page,
    theme,
    viewport,
):
    session_cookie = admin_client.get_cookie("session")
    browser_page.context.add_cookies(
        [{"name": "session", "value": session_cookie.value, "url": live_server}]
    )
    browser_page.set_viewport_size(viewport)
    browser_page.add_init_script(
        f"localStorage.setItem('theme', {json.dumps(theme)})"
    )
    browser_page.goto(
        f"{live_server}/demonstration/{seeded_data['demo_id']}?force_reload=1",
        wait_until="domcontentloaded",
    )

    toolbox = browser_page.locator("#toolbox-sidebar")
    toggle = toolbox.locator(".collapse-toggle")
    assert toolbox.is_visible()
    box = toolbox.bounding_box()
    assert box is not None
    assert box["x"] >= 0
    assert box["x"] + box["width"] <= viewport["width"] + 1
    assert browser_page.evaluate(
        "document.documentElement.scrollWidth <= window.innerWidth + 1"
    )

    assert toggle.get_attribute("aria-expanded") == "false"
    assert toolbox.locator("#public-toolbox-actions").is_hidden()
    assert toolbox.bounding_box()["width"] <= 53
    toggle.click()
    assert toggle.get_attribute("aria-expanded") == "true"
    assert toolbox.locator("#public-toolbox-actions").is_visible()
    assert toolbox.bounding_box()["width"] >= 270
