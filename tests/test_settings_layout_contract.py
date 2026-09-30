"""Shared layout, theme and safe-rendering contracts for account settings."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SETTINGS_TEMPLATE = ROOT / "mielenosoitukset_fi/templates/users/auth/settings.html"
WORKSPACE_CSS = ROOT / "mielenosoitukset_fi/static/css/user-workspace.css"
BASE_TEMPLATE = ROOT / "mielenosoitukset_fi/templates/base.html"


def test_settings_route_uses_shared_workspace_components(user_client):
    response = user_client.get("/users/auth/settings")

    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert 'class="container py-4 user-workspace-page user-settings-page"' in html
    assert 'class="user-page-heading"' in html
    assert 'class="user-settings-tabs__list" role="tablist"' in html
    for tab_id in ("general", "security", "tokens", "profile"):
        assert f'id="settings-tab-{tab_id}"' in html
        assert f'id="tab-{tab_id}" role="tabpanel"' in html
    assert 'class="user-form-section"' in html
    assert 'class="user-settings-card"' in html
    assert 'class="user-data-table"' in html
    assert 'class="form-check user-check-row' in html
    assert 'class="modal fade user-modal"' in html


def test_settings_template_has_no_page_owned_presentation_or_jquery_tabs():
    template = SETTINGS_TEMPLATE.read_text(encoding="utf-8")

    assert "<style" not in template
    assert re.search(r"\sstyle\s*=", template) is None
    assert "css/v2/settings.css" not in template
    assert "css/user/settings.css" not in template
    assert "jquery-ui.min.js" not in template
    assert "$(" not in template
    assert "settings-tab-activate" in template
    assert "ArrowRight" in template
    assert "ArrowLeft" in template


def test_settings_fields_and_city_picker_follow_accessible_contract():
    template = SETTINGS_TEMPLATE.read_text(encoding="utf-8")

    assert template.count('minlength="12"') == 2
    assert 'aria-describedby="new-password-help"' in template
    assert "user-city-picker__trigger" in template
    assert 'aria-controls="dropdown-content"' in template
    assert 'id="dropdown-content" role="listbox"' in template
    assert 'event.key === "Escape"' in template
    assert "option.hidden = !text.toUpperCase().includes(filter)" in template
    assert "option.setAttribute(\"aria-selected\", String(selected))" in template


def test_settings_api_data_is_rendered_with_dom_nodes_and_active_locale():
    template = SETTINGS_TEMPLATE.read_text(encoding="utf-8")

    assert "innerHTML" not in template
    assert "insertAdjacentHTML" not in template
    assert "document.createElement('tr')" in template
    assert "tokenList.replaceChildren(...rows)" in template
    assert "passkeysList.appendChild(card)" in template
    assert "document.documentElement.lang || 'fi'" in template
    assert "toLocaleString(\"fi-FI\"" not in template
    assert "toLocaleDateString(\"fi-FI\"" not in template


def test_settings_shared_css_uses_product_tokens_and_cache_is_bumped():
    css = WORKSPACE_CSS.read_text(encoding="utf-8")
    base = BASE_TEMPLATE.read_text(encoding="utf-8")

    for selector in (
        ".user-settings-tabs",
        ".user-settings-card",
        ".user-city-picker__menu",
        ".user-data-view__viewport",
        ".user-data-table",
        ".user-status-badge--success",
        ".user-form-feedback--success",
    ):
        assert selector in css
    assert "var(--product-surface)" in css
    assert "var(--product-text)" in css
    assert "var(--product-border)" in css
    assert "20260930-user-workspace-13" in base


def test_new_settings_copy_is_translated_in_supported_catalogs():
    expected = {
        "fi": ('msgstr "Asetusosiot"', 'msgstr "Todennuslaite"'),
        "en": ('msgstr "Settings sections"', 'msgstr "Authentication device"'),
        "sv": ('msgstr "Inställningsavsnitt"', 'msgstr "Autentiseringsenhet"'),
    }

    for locale, translations in expected.items():
        catalog = (
            ROOT
            / "mielenosoitukset_fi"
            / "translations"
            / locale
            / "LC_MESSAGES"
            / "messages.po"
        ).read_text(encoding="utf-8")
        for translation in translations:
            assert translation in catalog
