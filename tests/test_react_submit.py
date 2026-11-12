"""React wizard controls must preserve the existing submission/draft contract."""
import json
import re

import pytest
from playwright.sync_api import expect

from tests.test_submit_draft_reliability import DRAFT_KEY, install_quill_stub

pytestmark = [pytest.mark.e2e, pytest.mark.integration]
SUBMIT_MODULE = "**/frontend/assets/submit-*.js"


def open_form(page, base):
    install_quill_stub(page)
    page.goto(base + "/submit", wait_until="networkidle")
    expect(page.locator("#organizer_name_1")).to_be_attached()


def fill_valid_form(page):
    """Set native fields to valid values without submitting any real event."""
    page.evaluate(
        """() => {
          const values = {
            name: 'A retained demonstration', tags: 'test,rights',
            date: '2099-01-01', start_time: '12:00', type: 'paikallaan',
            address: 'A public square', organizer_name_1: 'Example organizer',
            submitter_role: 'organizer', submitter_name: 'Example submitter',
            submitter_email: 'submitter@example.test'
          };
          for (const [id, value] of Object.entries(values)) {
            const field = document.getElementById(id);
            field.value = value;
            field.dispatchEvent(new Event('input', { bubbles: true }));
            field.dispatchEvent(new Event('change', { bubbles: true }));
          }
          selectCity('Helsinki');
          document.getElementById('accept_terms').checked = true;
          showPage(5);
          window.dispatchEvent(new Event('pagehide'));
        }"""
    )
    assert page.evaluate("collectInvalidFields(document.getElementById('myForm')).map(e => e.id)") == []
    page.wait_for_function("key => JSON.parse(localStorage.getItem(key))?.fields.title === 'A retained demonstration'", arg=DRAFT_KEY)


def assert_draft_retained(page):
    expect(page.locator("#page-5")).to_be_visible()
    expect(page.locator("#submit-feedback")).to_be_visible()
    expect(page.locator("#submit-form")).to_be_enabled()
    assert page.locator("#name").input_value() == "A retained demonstration"
    assert page.evaluate("key => JSON.parse(localStorage.getItem(key)).fields.title", DRAFT_KEY) == "A retained demonstration"


def assert_delivered(page):
    expect(page.locator("#page-6")).to_be_visible()
    expect(page.locator(".progress-step[aria-current='step']")).to_have_attribute("data-page", "6")
    assert page.evaluate("key => localStorage.getItem(key)", DRAFT_KEY) is None


def install_modal_stub(page):
    # Test the controller's event/promise boundary without the blocked CDN script.
    page.add_init_script(
        """window.bootstrap = { Modal: class {
          static getOrCreateInstance(element) { return new this(element); }
          constructor(element) { this.element = element; }
          show() {
            this.element.style.display = 'block';
            this.element.classList.add('show');
            this.element.removeAttribute('aria-hidden');
            this.element.dispatchEvent(new Event('shown.bs.modal'));
          }
          hide() {
            this.element.style.display = 'none';
            this.element.classList.remove('show');
            this.element.setAttribute('aria-hidden', 'true');
            this.element.dispatchEvent(new Event('hidden.bs.modal'));
          }
        }};"""
    )


def test_react_navigation_validates_and_keeps_field_nodes(live_server, browser_page):
    page = browser_page
    open_form(page, live_server)
    expect(page.locator('[data-react-island="submit-choice"]')).to_have_attribute("data-react-mounted", "true")
    page.get_by_role("button", name="Lisää tiedot itse").click()
    expect(page.locator("#page-2")).to_be_visible()
    expect(page.locator("#page-2 .page-header h2")).to_be_focused()
    expect(page.locator(".progress-step[aria-current='step']")).to_have_attribute("data-page", "2")
    page.locator("#page-2").get_by_role("button", name=re.compile("Seuraava")).click()
    expect(page.locator("#name")).to_be_focused()
    expect(page.locator("#name")).to_have_attribute("aria-invalid", "true")
    expect(page.locator("#page-2")).to_be_visible()
    page.locator("#name").fill("Retain this field")
    page.locator("#tags").fill("rights")
    page.evaluate("window.__originalTitleField = document.getElementById('name')")
    page.locator("#page-2").get_by_role("button", name=re.compile("Seuraava")).click()
    expect(page.locator("#page-3 .page-header h2")).to_be_focused()
    expect(page.locator(".progress-step[aria-current='step']")).to_have_attribute("data-page", "3")
    page.locator("#page-3").get_by_role("button", name=re.compile("Edellinen")).click()
    expect(page.locator("#name")).to_have_value("Retain this field")
    assert page.evaluate("window.__originalTitleField === document.getElementById('name')")


def test_late_react_mount_keeps_restored_draft_step(live_server, browser_page):
    page = browser_page
    draft = {"version": 2, "step": 4, "fields": {"title": "Earlier draft"}, "organizers": []}
    page.add_init_script(
        f"localStorage.setItem({json.dumps(DRAFT_KEY)}, JSON.stringify({{...{json.dumps(draft)}, savedAt: Date.now()}}))"
    )
    page.route(SUBMIT_MODULE, lambda route: route.abort())
    open_form(page, live_server)
    expect(page.locator("#cacheNotice")).to_be_visible()
    expect(page.locator("#page-4")).to_be_visible()
    module_url = page.locator('script[src*="/frontend/assets/submit-"]').get_attribute("src")
    page.unroute(SUBMIT_MODULE)
    page.add_script_tag(url=live_server + module_url + "?late-mount-test=1", type="module")
    expect(page.locator('[data-react-island="submit-progress"]')).to_have_attribute("data-react-mounted", "true")
    expect(page.locator(".progress-step[aria-current='step']")).to_have_attribute("data-page", "4")
    expect(page.locator("#page-4")).to_be_visible()
    expect(page.locator("#name")).to_have_value("Earlier draft")
    assert not page.locator("#accept_terms").is_checked()


def test_failed_submit_module_retains_native_wizard_controls(live_server, browser_page):
    page = browser_page
    page.route(SUBMIT_MODULE, lambda route: route.abort())
    open_form(page, live_server)
    assert page.locator('[data-react-island="submit-progress"]').get_attribute("data-react-mounted") is None
    page.get_by_role("button", name="Tuo tiedot Facebookista").click()
    expect(page.locator("#facebook")).to_be_focused()
    expect(page.locator(".progress-step[aria-current='step']")).to_have_attribute("data-page", "2")
    page.locator("#page-2").get_by_role("button", name=re.compile("Seuraava")).click()
    expect(page.locator("#name")).to_be_focused()
    page.locator("#name").fill("Fallback demonstration")
    page.locator("#tags").fill("rights")
    page.locator("#page-2").get_by_role("button", name=re.compile("Seuraava")).click()
    expect(page.locator("#page-3")).to_be_visible()
    page.locator("#page-3").get_by_role("button", name=re.compile("Edellinen")).click()
    expect(page.locator("#name")).to_have_value("Fallback demonstration")


@pytest.mark.parametrize("failure", ["html", "malformed-json", "false-json", "network", "redirected-json"])
def test_failed_delivery_retains_draft_and_allows_confirmed_retry(live_server, browser_page, failure):
    page = browser_page
    posts = []

    def submit(route):
        if route.request.method != "POST":
            return route.continue_()
        posts.append(route.request.post_data)
        assert route.request.headers["x-requested-with"] == "XMLHttpRequest"
        if len(posts) > 1:
            return route.fulfill(status=200, content_type="application/json", body='{"success": true}')
        if failure == "network":
            return route.abort()
        if failure == "redirected-json":
            return route.fulfill(status=302, headers={"Location": "/submit-delivery-result"})
        content_type = "text/html" if failure == "html" else "application/json"
        body = {"html": "<h1>Maintenance page</h1>", "malformed-json": "{", "false-json": '{"success": false}'}[failure]
        route.fulfill(status=200, content_type=content_type, body=body)

    page.route("**/submit", submit)
    page.route("**/submit-delivery-result", lambda route: route.fulfill(status=200, content_type="application/json", body='{"success": true}'))
    open_form(page, live_server)
    fill_valid_form(page)
    page.locator("#submit-form").click()
    assert_draft_retained(page)
    assert len(posts) == 1
    page.locator("#submit-form").click()
    assert_delivered(page)
    assert len(posts) == 2


def test_force_retry_requires_confirmed_json_before_clearing_draft(live_server, browser_page):
    page = browser_page
    install_modal_stub(page)
    posts = []

    def submit(route):
        if route.request.method != "POST":
            return route.continue_()
        posts.append(route.request.post_data)
        if len(posts) == 1:
            return route.fulfill(status=409, content_type="application/json", body='{"conflict": true, "message": "Possible duplicate", "demos": []}')
        if len(posts) == 2:
            assert 'name="force_submit"' in posts[-1]
            return route.fulfill(status=200, content_type="text/html", body="<h1>Temporary outage</h1>")
        route.fulfill(status=200, content_type="application/json", body='{"success": true}')

    page.route("**/submit", submit)
    open_form(page, live_server)
    fill_valid_form(page)
    page.locator("#submit-form").click()
    expect(page.locator("#submitConflictModal")).to_be_visible()
    page.locator("#submit-conflict-confirm").click()
    assert_draft_retained(page)
    assert len(posts) == 2
    page.locator("#submit-form").click()
    assert_delivered(page)
    assert len(posts) == 3


def test_restored_draft_synchronizes_date_picker_alternate_inputs(live_server, browser_page):
    """Restoration must use the picker API so visible required inputs stay valid."""
    page = browser_page
    draft = {
        "version": 2, "step": 3,
        "fields": {"title": "A scheduled draft", "date": "2099-11-02", "start_time": "12:30"},
        "organizers": [],
    }
    page.add_init_script(
        f"localStorage.setItem({json.dumps(DRAFT_KEY)}, JSON.stringify({{...{json.dumps(draft)}, savedAt: Date.now()}}))"
    )
    # Model Flatpickr's documented altInput boundary. Changing the original
    # field's value alone intentionally does not update its visible control.
    page.add_init_script(
        """window.flatpickr = (selector, config) => {
          return [...document.querySelectorAll(selector)].map(original => {
            const alternate = document.createElement('input');
            alternate.type = 'text';
            alternate.required = original.required;
            alternate.dataset.pickerFor = original.id;
            original.type = 'hidden';
            original.insertAdjacentElement('afterend', alternate);
            const picker = {
              altInput: alternate,
              calendarContainer: document.createElement('div'),
              setDate(value) {
                original.value = value;
                alternate.value = config.altFormat === 'd.m.Y' && value
                  ? value.split('-').reverse().join('.') : value;
              }
            };
            original._flatpickr = picker;
            return picker;
          });
        };"""
    )
    open_form(page, live_server)
    expect(page.locator("#cacheNotice")).to_be_visible()
    expect(page.locator("#page-3")).to_be_visible()
    expect(page.locator("#date")).to_have_value("2099-11-02")
    expect(page.locator("#start_time")).to_have_value("12:30")
    expect(page.locator('[data-picker-for="date"]')).to_have_value("02.11.2099")
    expect(page.locator('[data-picker-for="start_time"]')).to_have_value("12:30")
    assert page.evaluate(
        """() => collectInvalidFields(document.getElementById('page-3'))
          .filter(field => ['date', 'start_time'].includes(field.dataset.pickerFor)).length"""
    ) == 0
    assert page.evaluate(
        """() => {
          const data = new FormData(document.getElementById('myForm'));
          return [data.get('date'), data.get('start_time')];
        }"""
    ) == ["2099-11-02", "12:30"]
