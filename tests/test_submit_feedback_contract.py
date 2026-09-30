import json
import re
from pathlib import Path

import pytest


TEMPLATE_PATH = Path("mielenosoitukset_fi/templates/submit.html")
WORKSPACE_CSS_PATH = Path("mielenosoitukset_fi/static/css/user-workspace.css")


def test_submit_form_uses_accessible_feedback_and_product_modal(client):
    response = client.get("/submit")

    assert response.status_code == 200
    page = response.get_data(as_text=True)

    assert 'id="myForm" class="user-form" novalidate' in page
    assert 'id="submit-feedback"' in page
    assert 'aria-live="polite"' in page
    assert 'aria-atomic="true"' in page
    assert 'id="submitConflictModal"' in page
    assert 'class="modal fade user-modal"' in page
    assert 'aria-labelledby="submitConflictModalLabel"' in page
    assert 'aria-describedby="submit-conflict-message"' in page
    assert 'id="submit-conflict-cancel"' in page
    assert 'id="submit-conflict-confirm"' in page


def test_submit_feedback_replaces_native_dialogs_and_marks_invalid_fields():
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    assert re.search(r"\balert\s*\(", template) is None
    assert re.search(r"(?:window\.)?confirm\s*\(", template) is None
    assert "showInvalidFields(invalidFields, SUBMIT_REQUIRED_ERROR)" in template
    assert "collectInvalidFields(currentPageElement)" in template
    assert "!field.disabled && field.willValidate && !field.checkValidity()" in template
    assert "field.setAttribute('aria-invalid', 'true')" in template
    assert "firstInvalid.focus({ preventScroll: true })" in template
    assert "if (pageNumber && pageNumber !== currentPage) showPage(pageNumber)" in template
    assert "submitFeedbackText.textContent = String(message || SUBMIT_GENERIC_ERROR)" in template
    assert "submitForm.addEventListener('input', clearDelegatedInvalidState)" in template
    assert "submitForm.addEventListener('change', clearDelegatedInvalidState)" in template


def test_submit_conflict_modal_renders_server_data_as_text_and_keeps_retry_contract():
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    assert "bootstrap.Modal.getOrCreateInstance(modalElement)" in template
    assert "messageElement.textContent = conflictData?.message || SUBMIT_CONFLICT_INTRO" in template
    assert "matchesElement.replaceChildren()" in template
    assert "item.textContent = parts.join(' | ')" in template
    assert "formData.set('force_submit', '1')" in template
    assert "response.status === 429 ? SUBMIT_RATE_LIMITED" in template
    assert "response.status !== 429 && data && data.message" in template
    assert "if (submittingDemo)" in template
    assert "submitBtn.disabled = true" in template
    assert "submitBtn.disabled = false" in template
    assert "submittingDemo = false" in template


def test_submit_feedback_has_shared_light_dark_component_and_cache_bump():
    workspace_css = WORKSPACE_CSS_PATH.read_text(encoding="utf-8")
    base = Path("mielenosoitukset_fi/templates/base.html").read_text(encoding="utf-8")

    assert ".user-form-feedback" in workspace_css
    assert ".user-form-feedback--error" in workspace_css
    assert "var(--product-danger-soft)" in workspace_css
    assert '[aria-invalid="true"]' in workspace_css
    assert ".user-conflict-list" in workspace_css
    assert "20260929-user-workspace-12" in base


def test_submit_new_feedback_copy_is_localized_in_english_and_swedish(app, client):
    app.config.update(
        BABEL_SUPPORTED_LOCALES=["fi", "en", "sv"],
        BABEL_PUBLIC_LOCALES=["fi", "en", "sv"],
    )
    for locale, expected_rate_limit, expected_confirm in (
        ("en", "Too many submission attempts. Wait a moment and try again.", "Submit anyway"),
        ("sv", "För många inskickningsförsök. Vänta en stund och försök igen.", "Skicka ändå"),
    ):
        with client.session_transaction() as session:
            session["locale"] = locale

        page = client.get("/submit").get_data(as_text=True)

        assert json.dumps(expected_rate_limit, ensure_ascii=True)[1:-1] in page
        assert expected_confirm in page


@pytest.mark.e2e
@pytest.mark.integration
def test_submit_validation_and_conflict_modal_work_in_browser(live_server, browser_page):
    browser_page.add_init_script(
        """
        (() => {
          const instances = new WeakMap();
          class Modal {
            constructor(element) {
              this.element = element;
              instances.set(element, this);
            }
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
            static getOrCreateInstance(element) {
              return instances.get(element) || new Modal(element);
            }
          }
          window.bootstrap = { Modal };
        })();
        """
    )
    browser_page.goto(f"{live_server}/submit", wait_until="domcontentloaded")

    assert browser_page.evaluate(
        """
        () => {
          const optionalUrl = document.createElement('input');
          optionalUrl.type = 'url';
          optionalUrl.value = 'not-a-url';
          document.getElementById('myForm').appendChild(optionalUrl);
          const detected = collectInvalidFields(document.getElementById('myForm')).includes(optionalUrl);
          optionalUrl.remove();
          return detected;
        }
        """
    )

    browser_page.evaluate("addOrganizer()")
    dynamic_name = browser_page.locator('[name^="organizer_name_"]').last
    dynamic_name.evaluate("element => element.setAttribute('aria-invalid', 'true')")
    dynamic_name.evaluate(
        """element => {
          element.value = 'Dynamic organizer';
          element.dispatchEvent(new Event('input', {bubbles: true}));
        }"""
    )
    assert dynamic_name.get_attribute("aria-invalid") is None

    browser_page.evaluate("showPage(5)")

    browser_page.locator("#submit-form").click()
    feedback = browser_page.locator("#submit-feedback")
    assert feedback.get_attribute("role") == "alert"
    assert browser_page.locator("#accept_terms").get_attribute("aria-invalid") == "true"
    assert browser_page.evaluate("document.activeElement.id") == "accept_terms"

    browser_page.locator("#accept_terms").check()
    browser_page.locator("#submit-form").click()
    assert browser_page.locator("#page-2").get_attribute("class") == "form-page active"
    assert browser_page.evaluate("document.activeElement.id") == "name"

    browser_page.evaluate(
        """
        () => {
          window.__submitConflictResult = null;
          confirmConflictSubmission({
            message: '<img src=x onerror=alert(1)>',
            demos: [{ title: '<strong>Safe title</strong>', date: '2026-10-01', address: 'Helsinki' }]
          }).then(result => { window.__submitConflictResult = result; });
        }
        """
    )
    modal = browser_page.locator("#submitConflictModal")
    modal.wait_for(state="visible")
    assert modal.locator("img").count() == 0
    assert modal.locator("strong").count() == 0
    assert modal.locator("#submit-conflict-message").text_content() == "<img src=x onerror=alert(1)>"
    assert "<strong>Safe title</strong>" in modal.locator("#submit-conflict-matches").text_content()
    modal.locator("#submit-conflict-confirm").click()
    browser_page.wait_for_function("window.__submitConflictResult === true")

    browser_page.evaluate(
        """
        async () => {
          const response = new Response(JSON.stringify({message: 'Raw backend rate-limit copy'}), {
            status: 429,
            headers: {'content-type': 'application/json'}
          });
          await showSubmitError(response);
        }
        """
    )
    assert "Lähetysyrityksiä on liian monta" in feedback.text_content()
    assert "Raw backend rate-limit copy" not in feedback.text_content()
