import json
from pathlib import Path

import pytest
from babel.messages import pofile

from tests.conftest import _seed_database


DETAIL = Path("mielenosoitukset_fi/templates/detail.html")
WORKSPACE_CSS = Path("mielenosoitukset_fi/static/css/user-workspace.css")


@pytest.mark.parametrize(
    ("locale", "expected"),
    [
        (
            "en",
            {
                "Ajankohta": "Date and time",
                "Tapahtumatyyppi": "Event type",
                "Näytä lisää": "Show more",
            },
        ),
        (
            "sv",
            {
                "Ajankohta": "Datum och tid",
                "Sijainti": "Plats",
                "Järjestäjät": "Arrangörer",
                "Tapahtumatyyppi": "Evenemangstyp",
                "Marssi": "Marsch",
                "Paikallaan": "Stationär demonstration",
                "Muu": "Annat",
                "Kuvaus": "Beskrivning",
                "Näytä lisää": "Visa mer",
            },
        ),
    ],
)
def test_event_overview_labels_are_translated(locale, expected):
    catalog_path = Path(
        f"mielenosoitukset_fi/translations/{locale}/LC_MESSAGES/messages.po"
    )
    with catalog_path.open("r", encoding="utf-8") as catalog_file:
        catalog = pofile.read_po(catalog_file)

    for message_id, translation in expected.items():
        assert catalog.get(message_id).string == translation


def test_event_detail_orders_core_information_before_secondary_actions():
    source = DETAIL.read_text(encoding="utf-8")

    hero = source.index('class="demo-hero site-hero')
    overview = source.index('class="demo-at-a-glance"', hero)
    cancellation = source.index("{% if demo.cancelled %}", overview)
    overview_description = source.index(
        "{{ event_description(collapsible=true) }}", cancellation
    )
    actions = source.index('class="action-buttons', overview_description)
    classic_description = source.index("{{ event_description() }}", actions)

    assert hero < overview < cancellation < overview_description < actions
    assert actions < classic_description
    assert 'aria-label="{{ _(\'Tapahtuman tiedot\') }}"' in source
    assert 'aria-controls="demo-description"' in source
    assert 'aria-expanded="false"' in source
    assert "data-description-accessible-preview" in source
    assert 'data-less-label="{{ _(\'Näytä vähemmän\') }}"' in source
    assert 'style="font-size: 1.1rem; line-height: 1.8;"' not in source
    assert "{% macro event_description(collapsible=false) %}" in source
    assert "{% set detail_layout = 'overview' %}" in source
    assert "{% if detail_layout == 'classic' %}" in source
    assert "{% if detail_layout == 'overview' %}" in source


def test_event_detail_hierarchy_uses_shared_responsive_workspace_styles():
    css = WORKSPACE_CSS.read_text(encoding="utf-8")

    assert ".demo-at-a-glance" in css
    assert ".event-description.is-collapsible:not(.is-expanded)" in css
    assert ".event-description.is-semantically-collapsed" in css
    assert ".event-description__preview[hidden]" in css
    assert ".event-description__toggle[hidden]" in css
    assert ".detail-layout-preference" in css
    assert ".event-description__content--classic" in css
    assert "grid-template-columns: 1fr;" in css


def test_event_detail_defaults_to_overview_and_exposes_layout_choice(
    client, seeded_data
):
    response = client.get(
        f"/demonstration/{seeded_data['demo_id']}?force_reload=1"
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'class="demo-at-a-glance"' in body
    assert '<section class="event-description user-data-card animate-fade-in-up"' in body
    assert 'class="demo-datetime"' not in body
    assert 'aria-label="Tapahtumasivun näkymä"' in body
    assert 'detail_layout=overview' in body
    assert 'detail_layout=classic' in body
    assert '/contact#contact-form-section' in body


def test_event_detail_layout_query_sets_scoped_cookie_and_redirects_canonically(
    client, seeded_data
):
    detail_path = f"/demonstration/{seeded_data['demo_id']}"
    response = client.get(
        f"{detail_path}?detail_layout=classic",
        base_url="https://example.test",
    )

    assert response.status_code == 302
    assert response.headers["Location"] == detail_path
    cookie = response.headers["Set-Cookie"]
    assert "detail-layout=classic" in cookie
    assert "Max-Age=31536000" in cookie
    assert "Secure" in cookie
    assert "HttpOnly" in cookie
    assert "Path=/demonstration/" in cookie
    assert "SameSite=Lax" in cookie

    classic = client.get(detail_path, base_url="https://example.test")
    body = classic.get_data(as_text=True)
    assert 'class="demo-datetime"' in body
    assert 'class="demo-at-a-glance"' not in body
    assert '<section class="event-description user-data-card animate-fade-in-up"' not in body
    assert 'event-description__content--classic' in body


def test_invalid_detail_layout_is_ignored_without_overwriting_preference(
    client, seeded_data
):
    detail_path = f"/demonstration/{seeded_data['demo_id']}"
    client.get(
        f"{detail_path}?detail_layout=classic",
        base_url="https://example.test",
    )

    invalid = client.get(
        f"{detail_path}?detail_layout=not-a-layout&force_reload=1",
        base_url="https://example.test",
    )
    assert invalid.status_code == 302
    assert invalid.headers["Location"] == f"{detail_path}?force_reload=1"
    assert "Set-Cookie" not in invalid.headers

    persisted = client.get(
        invalid.headers["Location"],
        base_url="https://example.test",
    )
    assert 'class="demo-datetime"' in persisted.get_data(as_text=True)


def test_detail_layout_cache_entries_do_not_cross_variants(client, seeded_data):
    detail_path = f"/demonstration/{seeded_data['demo_id']}"
    base_url = "https://example.test"

    overview_miss = client.get(detail_path, base_url=base_url)
    overview_hit = client.get(detail_path, base_url=base_url)
    assert overview_miss.headers["X-Cache"] == "MISS"
    assert overview_hit.headers["X-Cache"] == "HIT (cached)"
    assert 'class="demo-at-a-glance"' in overview_hit.get_data(as_text=True)

    client.get(
        f"{detail_path}?detail_layout=classic",
        base_url=base_url,
    )
    classic_miss = client.get(detail_path, base_url=base_url)
    classic_hit = client.get(detail_path, base_url=base_url)
    assert classic_miss.headers["X-Cache"] == "MISS"
    assert classic_hit.headers["X-Cache"] == "HIT (cached)"
    assert 'class="demo-datetime"' in classic_hit.get_data(as_text=True)
    assert 'class="demo-at-a-glance"' not in classic_hit.get_data(as_text=True)


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
    assert accessible_preview.is_visible()
    assert content.is_hidden()
    assert accessible_preview.text_content().strip()
    collapsed_accessibility = description.aria_snapshot()
    assert "Source 0" in collapsed_accessibility
    assert "Source 11" not in collapsed_accessibility
    clipped_links = content.locator('a[tabindex="-1"]')
    assert clipped_links.count() == 12
    assert browser_page.evaluate(
        "document.documentElement.scrollWidth <= window.innerWidth + 1"
    )

    toggle.click()

    assert toggle.get_attribute("aria-expanded") == "true"
    assert content.get_attribute("aria-hidden") is None
    assert accessible_preview.get_attribute("hidden") is not None
    assert content.is_visible()
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


@pytest.mark.e2e
@pytest.mark.integration
def test_detail_layout_choice_persists_across_event_pages(
    app, db, live_server, browser_page
):
    seeded = _seed_database(app, db)
    first_path = f"/demonstration/{seeded['demo_id']}"
    second_path = f"/demonstration/{seeded['child_demo_id']}"

    browser_page.goto(f"{live_server}{first_path}", wait_until="domcontentloaded")
    assert browser_page.locator(".demo-at-a-glance").is_visible()

    browser_page.get_by_role("link", name="Perinteinen").click()
    browser_page.wait_for_url(f"**{first_path}")
    assert "detail_layout" not in browser_page.url
    assert browser_page.locator(".demo-datetime").is_visible()
    assert browser_page.locator(".demo-at-a-glance").count() == 0
    assert browser_page.locator("[data-collapsible-description]").count() == 0

    browser_page.goto(f"{live_server}{second_path}", wait_until="domcontentloaded")
    assert browser_page.locator(".demo-datetime").is_visible()
    assert browser_page.locator(".demo-at-a-glance").count() == 0

    browser_page.get_by_role("link", name="Yleiskuva").click()
    browser_page.wait_for_url(f"**{second_path}")
    assert browser_page.locator(".demo-at-a-glance").is_visible()
    assert browser_page.get_by_role(
        "link", name="Anna palautetta tästä näkymästä"
    ).get_attribute("href").endswith("/contact#contact-form-section")
