"""Localization contracts for public suggestion and reminder feedback."""

from pathlib import Path

import pytest


REMINDER_MODAL = Path(
    "mielenosoitukset_fi/templates/_modals/reminder-modal.html"
)


def _set_locale(client, locale):
    with client.session_transaction() as browser_session:
        browser_session["locale"] = locale


@pytest.mark.parametrize(
    ("locale", "expected"),
    [
        ("fi", "Sähköpostiosoite vaaditaan."),
        ("en", "Email address is required."),
        ("sv", "E-postadress krävs."),
    ],
)
def test_reminder_api_localizes_required_email(app, client, seeded_data, locale, expected):
    app.config["BABEL_PUBLIC_LOCALES"] = ["fi", "en", "sv"]
    _set_locale(client, locale)

    response = client.post(f"/subscribe_reminder/{seeded_data['demo_id']}", data={})

    assert response.status_code == 200
    assert response.get_json() == {"status": "ERROR", "message": expected}


@pytest.mark.parametrize(
    ("locale", "expected"),
    [
        ("fi", "Kirjoita vähintään yksi kenttämuutos tai kommentti ennen lähettämistä."),
        ("en", "Enter at least one field change or comment before submitting."),
        ("sv", "Ange minst en fältändring eller kommentar innan du skickar."),
    ],
)
def test_suggestion_flash_localizes_empty_submission(
    app, client, seeded_data, locale, expected
):
    app.config["BABEL_PUBLIC_LOCALES"] = ["fi", "en", "sv"]
    _set_locale(client, locale)

    response = client.post(
        f"/suggest_change/{seeded_data['demo_id']}",
        data={},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert expected in response.get_data(as_text=True)


def test_reminder_modal_uses_shared_safe_feedback_contract():
    source = REMINDER_MODAL.read_text(encoding="utf-8")

    assert 'class="modal fade user-modal"' in source
    assert 'class="user-form-feedback"' in source
    assert 'role="status"' in source
    assert 'aria-live="polite"' in source
    assert 'aria-label="{{ _(&#39;Sulje&#39;) }}"' not in source
    assert 'aria-label="{{ _(\'Sulje\') }}"' in source
    assert "resultText.textContent" in source
    assert ".innerHTML" not in source
    assert "bootstrap.Modal.getOrCreateInstance" in source
    assert 'btn.setAttribute("aria-busy", "true")' in source
    assert 'modalEl.addEventListener("shown.bs.modal"' in source
    assert 'modalEl.addEventListener("hidden.bs.modal"' in source
