import json
from pathlib import Path

import pytest

from tests.conftest import _seed_database


DETAIL = Path("mielenosoitukset_fi/templates/detail.html")
WORKSPACE_CSS = Path("mielenosoitukset_fi/static/css/user-workspace.css")


def test_event_detail_orders_core_information_before_secondary_actions():
    source = DETAIL.read_text(encoding="utf-8")

    hero = source.index('class="demo-hero site-hero')
    overview = source.index('class="demo-at-a-glance"')
    cancellation = source.index("{% if demo.cancelled %}", overview)
    description = source.index('data-collapsible-description')
    actions = source.index('class="action-buttons')

    assert hero < overview < cancellation < description < actions
    assert 'aria-label="{{ _(\'Tapahtuman tiedot\') }}"' in source
    assert 'aria-controls="demo-description"' in source
    assert 'aria-expanded="false"' in source
    assert "data-description-accessible-preview" in source
    assert 'data-less-label="{{ _(\'Näytä vähemmän\') }}"' in source
    assert 'style="font-size: 1.1rem; line-height: 1.8;"' not in source


def test_event_detail_hierarchy_uses_shared_responsive_workspace_styles():
    css = WORKSPACE_CSS.read_text(encoding="utf-8")

    assert ".demo-at-a-glance" in css
    assert ".event-description.is-collapsible:not(.is-expanded)" in css
    assert ".event-description__toggle[hidden]" in css
    assert "grid-template-columns: 1fr;" in css


def test_event_detail_omits_missing_optional_organizers(
    admin_client, db, seeded_data
):
    db.demonstrations.update_one(
        {"_id": seeded_data["demo_id"]},
        {"$set": {"organizers": []}},
    )

    response = admin_client.get(
        f"/demonstration/{seeded_data['demo_id']}?force_reload=1"
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    overview = body[body.index('<dl class="demo-at-a-glance"'):body.index("</dl>")]
    assert "Järjestäjät" not in overview
    assert "Ei ilmoitettu" not in overview


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize(
    ("viewport_width", "theme"),
    [(390, "dark"), (1440, "light")],
)
def test_long_event_description_expands_across_viewports_and_themes(
    app, db, live_server, browser_page, viewport_width, theme
):
    seeded = _seed_database(app, db)
    db.demonstrations.update_one(
        {"_id": seeded["demo_id"]},
        {
            "$set": {
                "description": "".join(
                    (
                        f"""<p>Long accessible event description paragraph
                        {index}. <a href="https://example.test/{index}"
                        {" tabindex='2'" if index == 11 else ""}>
                        Source {index}</a>.</p>"""
                    )
                    for index in range(12)
                )
            }
        },
    )

    browser_page.set_viewport_size({"width": viewport_width, "height": 844})
    browser_page.add_init_script(
        f"localStorage.setItem('theme', {json.dumps(theme)})"
    )
    browser_page.goto(
        f"{live_server}/demonstration/{seeded['demo_id']}?force_reload=1",
        wait_until="domcontentloaded",
    )

    overview = browser_page.locator(".demo-at-a-glance")
    description = browser_page.locator("[data-collapsible-description]")
    toggle = browser_page.locator(".event-description__toggle")
    content = browser_page.locator(".event-description__content")
    accessible_preview = browser_page.locator(
        "[data-description-accessible-preview]"
    )

    assert overview.locator(".demo-at-a-glance__item").count() == 4
    assert toggle.is_visible()
    assert toggle.get_attribute("aria-expanded") == "false"
    assert content.get_attribute("aria-hidden") == "true"
    assert not accessible_preview.get_attribute("hidden")
    assert accessible_preview.text_content().strip()
    collapsed_accessibility = description.aria_snapshot()
    assert "Source 0" in collapsed_accessibility
    assert "Source 11" not in collapsed_accessibility
    assert content.evaluate("node => node.scrollHeight > node.clientHeight")
    clipped_links = content.locator('a[tabindex="-1"]')
    assert clipped_links.count() == 12
    assert browser_page.evaluate(
        "document.documentElement.scrollWidth <= window.innerWidth + 1"
    )

    toggle.click()

    assert toggle.get_attribute("aria-expanded") == "true"
    assert content.get_attribute("aria-hidden") is None
    assert accessible_preview.get_attribute("hidden") is not None
    assert content.evaluate("node => node.scrollHeight <= node.clientHeight + 1")
    assert content.locator('a[tabindex="-1"]').count() == 0
    assert content.locator("a").first.get_attribute("tabindex") is None
    assert content.locator("a").last.get_attribute("tabindex") == "2"
    assert "Source 11" in description.aria_snapshot()


@pytest.mark.e2e
@pytest.mark.integration
def test_description_recomputes_when_viewport_width_changes(
    app, db, live_server, browser_page
):
    seeded = _seed_database(app, db)
    db.demonstrations.update_one(
        {"_id": seeded["demo_id"]},
        {
            "$set": {
                "description": (
                    "<p>" + "Responsive event description text. " * 15 + "</p>"
                )
            }
        },
    )

    browser_page.set_viewport_size({"width": 1440, "height": 900})
    browser_page.goto(
        f"{live_server}/demonstration/{seeded['demo_id']}?force_reload=1",
        wait_until="domcontentloaded",
    )

    section = browser_page.locator("[data-collapsible-description]")
    toggle = browser_page.locator(".event-description__toggle")
    content = browser_page.locator(".event-description__content")

    assert toggle.is_hidden()
    assert "is-collapsible" not in (section.get_attribute("class") or "")
    assert content.get_attribute("aria-hidden") is None

    browser_page.set_viewport_size({"width": 390, "height": 844})
    toggle.wait_for(state="visible")

    assert "is-collapsible" in (section.get_attribute("class") or "")
    assert toggle.get_attribute("aria-expanded") == "false"
    assert content.get_attribute("aria-hidden") == "true"

    browser_page.set_viewport_size({"width": 1440, "height": 900})
    toggle.wait_for(state="hidden")

    assert "is-collapsible" not in (section.get_attribute("class") or "")
    assert content.get_attribute("aria-hidden") is None
