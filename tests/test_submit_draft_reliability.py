import json
from pathlib import Path

import pytest
from werkzeug.datastructures import MultiDict

from mielenosoitukset_fi.basic_routes import _collect_submission_organizers


TEMPLATE = Path("mielenosoitukset_fi/templates/submit.html")
DRAFT_SCRIPT = Path("mielenosoitukset_fi/static/js/submit-draft.js")
CITY_PARTIAL = Path("mielenosoitukset_fi/templates/paikkakunta-dropdown.html")
DRAFT_KEY = "mielenosoitukset.submit-draft.v2"


def install_quill_stub(browser_page):
    browser_page.add_init_script(
        """
        window.Quill = class Quill {
          constructor(selector) {
            this.container = document.querySelector(selector);
            this.root = document.createElement("div");
            this.root.className = "ql-editor";
            this.root.contentEditable = "true";
            this.container.appendChild(this.root);
            this.handlers = [];
            this.root.addEventListener("input", () => {
              this.handlers.forEach((handler) => handler());
            });
            this.clipboard = {
              convert: (html) => {
                const element = document.createElement("div");
                element.innerHTML = html;
                return {ops: [{insert: `${element.textContent}\\n`}]} ;
              },
            };
          }
          getContents() {
            return {ops: [{insert: `${this.root.textContent}\\n`}]} ;
          }
          setContents(delta) {
            this.root.textContent = delta.ops.map((operation) => operation.insert).join("");
          }
          on(eventName, handler) {
            if (eventName === "text-change") this.handlers.push(handler);
          }
        };
        """
    )


def test_submit_draft_contract_is_scoped_versioned_and_exactly_cleared():
    template = TEMPLATE.read_text(encoding="utf-8")
    script = DRAFT_SCRIPT.read_text(encoding="utf-8")
    city_partial = CITY_PARTIAL.read_text(encoding="utf-8")

    assert "20261004-submit-draft-1" in template
    assert DRAFT_KEY in script
    assert "DRAFT_TTL_MS = 24 * 60 * 60 * 1000" in script
    assert 'const form = document.getElementById("myForm")' in script
    assert 'storageRemove(DRAFT_KEY)' in script
    assert "submission_token" not in script
    assert "accept_terms" not in script
    assert 'field.type === "file"' in script
    assert "normalizeDelta" in script
    assert 'quill.setContents(delta, "silent")' in script
    assert "document.querySelectorAll(\"input, select, textarea\")" not in template
    assert "window.clearSubmitDraft?.();" in template
    assert 'dispatchEvent(new Event("change", { bubbles: true }))' in city_partial


def test_sparse_organizer_indexes_are_collected_in_numeric_order():
    organizers = _collect_submission_organizers(
        MultiDict(
            [
                ("organizer_name_3", " Third "),
                ("organizer_email_3", "third@example.test"),
                ("organizer_is_private_3", "on"),
                ("organizer_name_1", " First "),
                ("organizer_website_1", "https://first.example.test"),
                ("organizer_show_name_1", "on"),
                ("organizer_show_email_1", "on"),
            ]
        )
    )

    assert [organizer.name for organizer in organizers] == ["First", "Third"]
    assert organizers[0].website == "https://first.example.test"
    assert organizers[1].email == "third@example.test"
    assert organizers[0].is_private is False
    assert organizers[0].show_name_public is True
    assert organizers[0].show_email_public is True
    assert organizers[1].is_private is True
    assert organizers[1].show_name_public is False
    assert organizers[1].show_email_public is False


def test_submit_draft_notice_is_localized_in_english_and_swedish(app, client):
    app.config.update(
        BABEL_SUPPORTED_LOCALES=["fi", "en", "sv"],
        BABEL_PUBLIC_LOCALES=["fi", "en", "sv"],
    )
    for locale, notice, reset in (
        (
            "en",
            "Draft restored from this browser. It will be deleted automatically after 24 hours.",
            "Delete draft and start over",
        ),
        (
            "sv",
            "Utkastet återställdes från den här webbläsaren. Det raderas automatiskt efter 24 timmar.",
            "Radera utkastet och börja om",
        ),
    ):
        with client.session_transaction() as session:
            session["locale"] = locale

        page = client.get("/submit").get_data(as_text=True)
        assert notice in page
        assert reset in page


@pytest.mark.e2e
@pytest.mark.integration
def test_clean_submit_page_preserves_server_defaults(live_server, browser_page):
    browser_page.goto(f"{live_server}/submit", wait_until="domcontentloaded")

    token = browser_page.locator('[name="submission_token"]').input_value()
    language = browser_page.locator("#default_language").input_value()

    assert token
    assert language in {"fi", "en", "sv"}
    assert browser_page.evaluate(
        "key => window.localStorage.getItem(key)", DRAFT_KEY
    ) is None
    assert browser_page.locator("#accept_terms").is_checked() is False


@pytest.mark.e2e
@pytest.mark.integration
def test_submit_draft_restores_fields_quill_city_and_organizers(
    live_server, browser_page
):
    install_quill_stub(browser_page)
    browser_page.goto(f"{live_server}/submit", wait_until="domcontentloaded")
    editor = browser_page.locator(".ql-editor")
    editor.wait_for(state="attached")
    browser_page.evaluate("showPage(2)")
    editor.wait_for(state="visible")
    original_token = browser_page.locator('[name="submission_token"]').input_value()

    browser_page.locator("#name").fill("Restored demonstration")
    browser_page.locator("#default_language").select_option("en")
    browser_page.evaluate("selectCity('Helsinki')")
    editor.fill("Saved description")

    browser_page.evaluate("showPage(5)")
    browser_page.locator("#submitter_email").fill("submitter@example.test")
    browser_page.locator("#accept_terms").check()

    browser_page.evaluate("showPage(4)")
    browser_page.locator("#organizer_name_1").fill("First organizer")
    browser_page.locator("#organizer_email_1").fill("first@example.test")
    browser_page.evaluate("addOrganizer()")
    browser_page.locator("#organizer_name_2").fill("Second organizer")
    browser_page.locator("#organizer_is_private_2").check()
    browser_page.locator("#organizer_show_name_2").uncheck()
    browser_page.evaluate("window.saveSubmitDraft();")
    browser_page.wait_for_function(
        """
        key => {
          const value = window.localStorage.getItem(key);
          if (!value) return false;
          const draft = JSON.parse(value);
          return draft.organizers?.[1]?.isPrivate === true
            && draft.organizers?.[1]?.showName === false;
        }
        """,
        arg=DRAFT_KEY,
    )

    stored = json.loads(
        browser_page.evaluate("key => window.localStorage.getItem(key)", DRAFT_KEY)
    )
    assert stored["version"] == 2
    assert stored["step"] == 4
    assert stored["fields"]["title"] == "Restored demonstration"
    assert stored["fields"]["city"] == "Helsinki"
    assert len(stored["organizers"]) == 2
    assert "accept_terms" not in stored["fields"]
    assert "submission_token" not in stored["fields"]
    assert "image" not in stored["fields"]
    assert "descriptionDelta" in stored

    browser_page.evaluate("showPage(3)")
    browser_page.locator("#type").select_option("marssi")
    browser_page.locator("#route").fill("Station, Square")
    browser_page.evaluate("showPage(4)")
    browser_page.evaluate("window.saveSubmitDraft();")
    browser_page.wait_for_function(
        "key => JSON.parse(window.localStorage.getItem(key)).fields.route === 'Station, Square'",
        arg=DRAFT_KEY,
    )

    browser_page.reload(wait_until="domcontentloaded")
    editor = browser_page.locator(".ql-editor")
    editor.wait_for(state="attached")
    browser_page.locator("#cacheNotice:not(.hidden)").wait_for(state="visible")

    assert browser_page.locator("#name").input_value() == "Restored demonstration"
    assert browser_page.locator("#default_language").input_value() == "en"
    assert browser_page.locator("#selected-city").input_value() == "Helsinki"
    assert browser_page.locator(".dropbtn").text_content() == "Helsinki"
    assert browser_page.locator("#submitter_email").input_value() == "submitter@example.test"
    assert browser_page.locator("#organizer_name_1").input_value() == "First organizer"
    assert browser_page.locator("#organizer_name_2").input_value() == "Second organizer"
    assert browser_page.locator("#organizer_is_private_2").is_checked()
    assert browser_page.locator("#organizer_show_name_2").is_checked() is False
    assert editor.text_content().strip() == "Saved description"
    assert browser_page.locator("#accept_terms").is_checked() is False
    assert browser_page.locator('[name="submission_token"]').input_value()
    assert browser_page.locator('[name="submission_token"]').input_value() != original_token
    assert browser_page.locator("#page-4").get_attribute("class") == "form-page active"
    assert browser_page.locator("#march-route-container").evaluate(
        "element => element.style.display"
    ) == "block"
    assert browser_page.locator("#route-preview-list").text_content() == "StationSquare"


@pytest.mark.e2e
@pytest.mark.integration
def test_submit_draft_flushes_pending_edits_on_pagehide(live_server, browser_page):
    browser_page.goto(f"{live_server}/submit", wait_until="domcontentloaded")
    browser_page.wait_for_timeout(50)
    browser_page.evaluate("showPage(2)")
    browser_page.locator("#name").fill("Last-second edit")
    browser_page.evaluate("window.dispatchEvent(new Event('pagehide'))")

    stored = json.loads(
        browser_page.evaluate("key => window.localStorage.getItem(key)", DRAFT_KEY)
    )
    assert stored["fields"]["title"] == "Last-second edit"


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize("stored_value", ["{bad json", "expired"])
def test_invalid_submit_draft_fails_open_without_clearing_server_defaults(
    live_server, browser_page, stored_value
):
    if stored_value == "expired":
        stored_value = json.dumps(
            {
                "version": 2,
                "savedAt": 1,
                "step": 999,
                "fields": {"default_language": "sv", "title": "Expired"},
                "organizers": [],
            }
        )
    browser_page.add_init_script(
        f"window.localStorage.setItem({json.dumps(DRAFT_KEY)}, {json.dumps(stored_value)});"
    )
    browser_page.goto(f"{live_server}/submit", wait_until="domcontentloaded")

    assert browser_page.locator('[name="submission_token"]').input_value()
    assert browser_page.locator("#default_language").input_value() in {"fi", "en", "sv"}
    assert browser_page.locator("#name").input_value() == ""
    assert browser_page.locator("#page-1").get_attribute("class") == "form-page active"
    assert browser_page.evaluate(
        "key => window.localStorage.getItem(key)", DRAFT_KEY
    ) is None
