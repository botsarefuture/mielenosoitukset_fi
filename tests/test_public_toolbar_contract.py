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


def test_toolbar_uses_safe_management_links_instead_of_duplicate_handlers():
    source = _template_source()

    assert "<style" not in source
    assert "confirm(" not in source
    assert "acceptDemo(" not in source
    assert "rejectDemo(" not in source
    assert "openModal(" not in source
    assert "leaveOrganization(" not in source
    assert "fetchDemoInfo(" not in source
    assert "admin_demo.demo_command_center" in source
    assert "admin_demo.confirm_delete_demo" in source
    assert "admin_org.view_organization" in source
    assert "admin_org.confirm_delete_organization" in source
    assert 'demo_permissions.get("VIEW_DEMO")' in source
    assert 'org_permissions.get("VIEW_ORGANIZATION")' in source
    assert 'current_user.has_permission("VIEW_DEMO")' not in source


def test_toolbar_uses_clear_action_hierarchy_without_current_page_links():
    source = _template_source()

    assert "public-toolbox__action--primary" in source
    assert "public-toolbox__action--danger" in source
    assert "url_for('demonstration_detail'" not in source
    assert "url_for('org'" not in source
    assert "stats-content" not in source
    assert "invite_modal" not in source


def test_toolbar_collapse_control_exposes_state_and_relationship():
    source = _template_source()

    assert 'aria-controls="public-toolbox-actions"' in source
    assert 'aria-expanded="true"' in source
    assert 'id="public-toolbox-actions" hidden' not in source
    assert "body.hidden = collapsed" in source
    assert "setToolboxCollapsed(true)" in source
    assert "toggle.setAttribute('aria-expanded', String(!collapsed))" in source
    assert "data-collapse-label" in source
    assert "data-expand-label" in source
    assert "querySelectorAll('[data-js-only]')" in source


def test_toolbar_styles_are_scoped_and_use_product_tokens():
    source = _stylesheet_source()

    assert ".public-toolbox" in source
    assert ".public-toolbox__header" in source
    assert ".public-toolbox__actions" in source
    assert ".public-toolbox__action--primary" in source
    assert ".public-toolbox__action--danger" in source
    assert ".public-toolbox__body[hidden]" in source
    assert "@media (max-width: 35rem)" in source
    assert "focus-visible" in source
    assert "max-height: calc(100dvh" in source
    assert "overflow-y: auto" in source
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

    assert "20261001-public-toolbox-2" in source


def test_toolbar_renders_for_authenticated_admin_demo_context(
    admin_client, seeded_data
):
    response = admin_client.get(
        f"/demonstration/{seeded_data['demo_id']}?force_reload=1"
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'id="toolbox-sidebar"' in body
    assert 'aria-controls="public-toolbox-actions"' in body
    assert 'id="public-toolbox-actions" hidden' not in body
    assert 'aria-expanded="true"' in body
    assert f'/admin/demo/command-center/{seeded_data["demo_id"]}' in body
    assert f'/admin/demo/confirm_delete_demo/{seeded_data["demo_id"]}' in body


def test_toolbar_hides_javascript_only_controls_until_enhanced(
    admin_client, seeded_data
):
    response = admin_client.get(
        f"/demonstration/{seeded_data['demo_id']}?force_reload=1"
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'data-js-only hidden onclick="toggleToolbox()"' in body
    assert body.count("data-js-only hidden") == 1


def test_toolbar_renders_organization_management_links(admin_client, seeded_data):
    response = admin_client.get(f"/organization/{seeded_data['org_id']}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'id="toolbox-sidebar"' in body
    assert f'/admin/organization/view/{seeded_data["org_id"]}' in body
    assert f'/admin/organization/edit/{seeded_data["org_id"]}' in body
    assert f'/admin/organization/confirm_delete/{seeded_data["org_id"]}' in body
    assert 'id="inviteModal"' not in body


def test_toolbar_is_omitted_when_role_has_no_contextual_actions(
    translator_client, seeded_data
):
    response = translator_client.get(
        f"/demonstration/{seeded_data['demo_id']}?force_reload=1"
    )

    assert response.status_code == 200
    assert 'id="toolbox-sidebar"' not in response.get_data(as_text=True)


def test_organization_admin_with_regular_user_role_gets_scoped_toolbox(
    user_client, seeded_data
):
    response = user_client.get(f"/organization/{seeded_data['org_id']}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'id="toolbox-sidebar"' in body
    assert f'/admin/organization/view/{seeded_data["org_id"]}' in body
    assert f'/admin/organization/edit/{seeded_data["org_id"]}' in body
    assert f'/admin/organization/confirm_delete/{seeded_data["org_id"]}' not in body


def test_organization_scope_does_not_leak_to_unrelated_demonstration(
    user_client, seeded_data
):
    response = user_client.get(
        f"/demonstration/{seeded_data['demo_id']}?force_reload=1"
    )

    assert response.status_code == 200
    assert 'id="toolbox-sidebar"' not in response.get_data(as_text=True)


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
        ("dark", {"width": 390, "height": 568}),
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
    expanded_box = toolbox.bounding_box()
    assert expanded_box["y"] + expanded_box["height"] <= viewport["height"] + 1
