"""The React submission page: wizard, draft and delivery behaviour in a browser.

These replace the legacy wizard assertions (`window.showPage`,
`collectInvalidFields`, `#page-N.active`) with the React DOM. The guarantees
under test are unchanged: validate before advancing, keep the draft when
delivery is not confirmed, clear it only on an explicit JSON success.
"""
import json
import re

import pytest
from playwright.sync_api import expect

from tests.test_submit_draft_reliability import DRAFT_KEY

pytestmark = [pytest.mark.e2e, pytest.mark.integration]
REACT_MODULE = "**/frontend/assets/submitReact-*.js"


def enable_react(app):
    app.config["PUBLIC_SUBMIT_REACT_ENABLED"] = True


def open_react_form(page, base):
    page.goto(base + "/submit", wait_until="networkidle")
    island = page.locator('[data-react-island="submit-page"]')
    expect(island).to_have_attribute("data-react-mounted", "true")
    return island


def fill_page_two(page):
    page.get_by_role("button", name="Lisää tiedot itse").click()
    expect(page.locator("#page-2")).to_be_visible()
    page.locator("#name").fill("React demonstration")
    page.locator("#tags").fill("test,rights")
    page.locator("#page-2").get_by_role("button", name=re.compile("Seuraava")).click()
    expect(page.locator("#page-3")).to_be_visible()


def fill_page_three(page):
    # Flatpickr owns the visible Finnish field (d.m.Y); the hidden input carries ISO.
    page.evaluate("document.getElementById('date-display')._flatpickr.setDate('01.01.2099', true)")
    page.evaluate("document.getElementById('start_time-display')._flatpickr.setDate('12:00', true)")
    assert page.evaluate("document.getElementById('date').value") == "2099-01-01"
    assert page.evaluate("document.getElementById('start_time').value") == "12:00"
    page.locator("#type").select_option("paikallaan")
    page.locator("#city-trigger").click()
    page.locator(".submit-city__option", has_text="Helsinki").first.click()
    page.locator("#address").fill("A public square")
    page.locator("#page-3").get_by_role("button", name=re.compile("Seuraava")).click()
    expect(page.locator("#page-4")).to_be_visible()


def fill_page_four(page):
    page.locator("#organizer_name_1").fill("Example organizer")
    page.locator("#page-4").get_by_role("button", name=re.compile("Seuraava")).click()
    expect(page.locator("#page-5")).to_be_visible()


def fill_contact(page):
    page.locator("#submitter_role").fill("organizer")
    page.locator("#submitter_name").fill("Example submitter")
    page.locator("#submitter_email").fill("submitter@example.test")
    page.locator("#accept_terms").check()


def test_wizard_validates_before_advancing_and_focuses_the_problem(app, page_one_ready):
    page = page_one_ready
    page.get_by_role("button", name="Lisää tiedot itse").click()
    expect(page.locator("#page-2")).to_be_visible()

    page.locator("#page-2").get_by_role("button", name=re.compile("Seuraava")).click()
    # Still on page 2, the invalid field is announced and focused.
    expect(page.locator("#page-2")).to_be_visible()
    expect(page.locator("#name")).to_have_attribute("aria-invalid", "true")
    expect(page.locator("#name")).to_be_focused()
    expect(page.locator("#submit-feedback")).to_be_visible()

    page.locator("#name").fill("Retained title")
    page.locator("#tags").fill("rights")
    page.locator("#page-2").get_by_role("button", name=re.compile("Seuraava")).click()
    expect(page.locator("#page-3")).to_be_visible()
    expect(page.locator(".progress-step[aria-current='step']")).to_have_attribute("data-page", "3")

    page.locator("#page-3").get_by_role("button", name=re.compile("Edellinen")).click()
    expect(page.locator("#page-2")).to_be_visible()
    expect(page.locator("#name")).to_have_value("Retained title")


def test_draft_is_retained_until_json_success_confirms_delivery(app, page_one_ready):
    page = page_one_ready
    posts = []

    def submit(route):
        if route.request.method != "POST":
            return route.continue_()
        posts.append(route.request.post_data)
        assert route.request.headers["x-requested-with"] == "XMLHttpRequest"
        if len(posts) == 1:
            return route.fulfill(status=200, content_type="text/html", body="<h1>Outage</h1>")
        return route.fulfill(status=200, content_type="application/json", body='{"success": true}')

    page.route("**/submit", submit)

    fill_page_two(page)
    fill_page_three(page)
    fill_page_four(page)
    fill_contact(page)

    page.wait_for_function(
        "key => JSON.parse(localStorage.getItem(key))?.fields.title === 'React demonstration'", arg=DRAFT_KEY
    )

    page.locator("#submit-form").click()
    expect(page.locator("#submit-feedback")).to_be_visible()
    expect(page.locator("#submit-form")).to_be_enabled()
    assert len(posts) == 1
    page.wait_for_function(
        "key => JSON.parse(localStorage.getItem(key))?.fields.title === 'React demonstration'", arg=DRAFT_KEY
    )

    page.locator("#submit-form").click()
    expect(page.locator("#page-6")).to_be_visible()
    expect(page.locator(".progress-step[aria-current='step']")).to_have_attribute("data-page", "6")
    assert page.evaluate("key => localStorage.getItem(key)", DRAFT_KEY) is None
    assert len(posts) == 2
    # Organizers and terms still cross the wire under the legacy field names.
    assert "organizer_name_1" in posts[-1]
    assert 'name="accept_terms"' in posts[-1]


def test_restored_draft_rehydrates_fields_and_step(app, live_server, browser_page):
    enable_react(app)
    draft = {
        "version": 2,
        "step": 4,
        "savedAt": 4102444800000,  # fixed recent-enough timestamp, refreshed below
        "fields": {"title": "Earlier draft", "tags": "rights", "date": "2099-11-02", "start_time": "12:30"},
        "organizers": [{"name": "Restored org", "email": "", "website": "", "isPrivate": False, "showName": True, "showEmail": True}],
    }
    # Seed before the page loads so the pagehide flush of an empty form cannot race it.
    browser_page.add_init_script(
        f"localStorage.setItem({json.dumps(DRAFT_KEY)}, JSON.stringify({{...{json.dumps(draft)}, savedAt: Date.now()}}))"
    )
    page = browser_page
    open_react_form(page, live_server)

    expect(page.locator("#cacheNotice")).to_be_visible()
    expect(page.locator("#page-4")).to_be_visible()
    expect(page.locator(".progress-step[aria-current='step']")).to_have_attribute("data-page", "4")
    expect(page.locator("#organizer_name_1")).to_have_value("Restored org")
    expect(page.locator("#name")).to_have_value("Earlier draft")
    # ISO draft values are re-rendered in the visible Finnish format.
    expect(page.locator("#date-display")).to_have_value("02.11.2099")
    expect(page.locator("#start_time-display")).to_have_value("12:30")
    assert page.evaluate("document.getElementById('date').value") == "2099-11-02"


@pytest.fixture
def page_one_ready(app, live_server, browser_page):
    enable_react(app)
    open_react_form(browser_page, live_server)
    return browser_page


@pytest.mark.parametrize("width", [390, 1440])
def test_steps_do_not_overflow_horizontally(app, live_server, browser_page, width):
    """Every step stays inside the viewport at mobile and desktop widths."""
    enable_react(app)
    browser_page.set_viewport_size({"width": width, "height": 900})
    page = browser_page
    open_react_form(page, live_server)

    def assert_fits(step):
        expect(page.locator(f"#page-{step}")).to_be_visible()
        assert page.evaluate(
            "document.documentElement.scrollWidth <= window.innerWidth + 1"
        ), f"step {step} overflows at {width}px"

    assert_fits(1)
    fill_page_two(page)
    assert_fits(3)
    fill_page_three(page)
    assert_fits(4)
    fill_page_four(page)
    assert_fits(5)


def test_date_and_time_fields_render_one_visible_control_each(app, live_server, browser_page):
    """Regression: Flatpickr's altInput left the original visible beside a duplicate."""
    enable_react(app)
    page = browser_page
    open_react_form(page, live_server)
    fill_page_two(page)  # the fields must be on a visible step to measure them

    # Each field has exactly one visible, focusable control plus one hidden ISO field.
    for field in ("date", "start_time", "end_time"):
        visible = page.evaluate(
            """id => [...document.getElementById(`${id}-display`).closest('.form-group').querySelectorAll('input')]
                 .filter(el => el.type !== 'hidden' && el.getBoundingClientRect().height > 0).length""",
            field,
        )
        assert visible == 1, (field, visible)
        assert page.evaluate("id => document.getElementById(id).type", field) == "hidden"
        assert page.evaluate("id => document.getElementById(`${id}-display`)._flatpickr !== undefined", field) is True

    # The required attribute sits on the control the user actually sees/uses.
    assert page.evaluate("() => document.getElementById('date-display').required") is True

    # Selecting a date fills the visible Finnish field and the hidden ISO value.
    page.evaluate("document.getElementById('date-display')._flatpickr.setDate('01.01.2099', true)")
    assert page.locator("#date-display").input_value() == "01.01.2099"
    assert page.evaluate("document.getElementById('date').value") == "2099-01-01"


def test_city_picker_opens_anchored_and_records_the_choice(app, live_server, browser_page):
    enable_react(app)
    page = browser_page
    open_react_form(page, live_server)
    fill_page_two(page)

    trigger = page.locator("#city-trigger")
    panel = page.locator(".submit-city__panel")
    expect(panel).to_have_count(0)
    trigger.click()
    expect(panel).to_be_visible()

    # The panel is anchored under the trigger instead of escaping to an ancestor.
    geometry = page.evaluate(
        """() => {
          const t = document.getElementById('city-trigger').getBoundingClientRect();
          const p = document.querySelector('.submit-city__panel').getBoundingClientRect();
          return {gap: Math.round(p.top - t.bottom), widthDelta: Math.abs(Math.round(p.width - t.width)),
                  viewport: window.innerHeight, panelBottom: Math.round(p.bottom)};
        }"""
    )
    assert abs(geometry["gap"]) <= 8, geometry
    assert geometry["widthDelta"] <= 2, geometry

    page.locator(".submit-city__option", has_text="Helsinki").first.click()
    expect(panel).to_have_count(0)
    expect(trigger).to_contain_text("Helsinki")
    assert page.evaluate("document.getElementById('city-value').value") == "Helsinki"

    # Keyboard: Escape closes without changing the value.
    trigger.click()
    expect(panel).to_be_visible()
    page.keyboard.press("Escape")
    expect(panel).to_have_count(0)
    assert page.evaluate("document.getElementById('city-value').value") == "Helsinki"


def test_deleting_the_draft_clears_it_and_it_stays_cleared(app, live_server, browser_page):
    """Reported bug: "Poista luonnos" reloaded but the draft came straight back."""
    enable_react(app)
    page = browser_page
    draft = {"version": 2, "step": 2, "fields": {"title": "Old draft"}, "organizers": []}
    # Seed once only: an init script runs on every navigation, including the reload.
    page.add_init_script(
        f"if (!sessionStorage.getItem('seeded')) {{ sessionStorage.setItem('seeded', '1');"
        f" localStorage.setItem({json.dumps(DRAFT_KEY)}, JSON.stringify({{...{json.dumps(draft)}, savedAt: Date.now()}})); }}"
    )
    page.goto(live_server + "/submit", wait_until="networkidle")

    expect(page.locator("#cacheNotice")).to_be_visible()
    expect(page.locator("#name")).to_have_value("Old draft")

    page.locator("#resetCacheBtn").click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(600)

    assert page.evaluate("key => localStorage.getItem(key)", DRAFT_KEY) is None
    expect(page.locator("#cacheNotice")).to_have_count(0)
    expect(page.locator("#name")).to_have_value("")
    expect(page.locator(".progress-step[aria-current='step']")).to_have_attribute("data-page", "1")

    # An untouched form must not re-create a draft on the next visit.
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(600)
    assert page.evaluate("key => localStorage.getItem(key)", DRAFT_KEY) is None
    expect(page.locator("#cacheNotice")).to_have_count(0)


def test_route_section_appears_only_for_marssi(app, live_server, browser_page):
    """Reported bug: `.optional-section { display: none }` hid the route fields."""
    enable_react(app)
    page = browser_page
    open_react_form(page, live_server)
    fill_page_two(page)

    route = page.locator("#march-route-container")
    expect(route).to_have_count(0)

    page.locator("#type").select_option("marssi")
    expect(route).to_be_visible()
    assert page.evaluate("Math.round(document.getElementById('march-route-container').getBoundingClientRect().height)") > 100

    page.locator("#route").fill("Rautatientori, Mannerheimintie, Eduskuntatalo")
    expect(page.locator("#route-preview li")).to_have_count(3)

    page.locator("#type").select_option("paikallaan")
    expect(route).to_have_count(0)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_calendar_panel_is_readable_in_both_themes(app, live_server, browser_page, theme):
    """Reported bug: the Flatpickr panel stayed white with light text in dark mode."""
    enable_react(app)
    page = browser_page
    page.add_init_script(f"localStorage.setItem('theme', '{theme}')")
    page.goto(live_server + "/submit", wait_until="networkidle")
    fill_page_two(page)

    page.locator("#date-display").click()
    page.wait_for_selector(".flatpickr-calendar.open")

    contrast = page.evaluate(
        """() => {
          const parse = c => c.match(/\\d+/g).slice(0, 3).map(Number);
          const luminance = rgb => {
            const [r, g, b] = rgb.map(v => {
              const n = v / 255;
              return n <= 0.03928 ? n / 12.92 : Math.pow((n + 0.055) / 1.055, 2.4);
            });
            return 0.2126 * r + 0.7152 * g + 0.0722 * b;
          };
          const cal = document.querySelector('.flatpickr-calendar.open');
          const day = cal.querySelector('.flatpickr-day:not(.prevMonthDay):not(.nextMonthDay)');
          const bg = parse(getComputedStyle(cal).backgroundColor);
          const fg = parse(getComputedStyle(day).color);
          const [a, b] = [luminance(bg), luminance(fg)].sort((x, y) => y - x);
          return {ratio: (a + 0.05) / (b + 0.05), bg, fg,
                  dark: document.documentElement.classList.contains('dark')};
        }"""
    )
    assert contrast["dark"] is (theme == "dark")
    assert contrast["ratio"] >= 4.5, contrast
    if theme == "dark":
        # The panel must not keep Flatpickr's light default.
        assert contrast["bg"] != [255, 255, 255], contrast
