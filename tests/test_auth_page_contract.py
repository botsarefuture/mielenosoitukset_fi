"""Focused contracts for the shared login and registration experience."""

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
LOGIN_TEMPLATE = ROOT / "mielenosoitukset_fi/templates/users/auth/login.html"
REGISTER_TEMPLATE = ROOT / "mielenosoitukset_fi/templates/users/auth/register.html"
AUTH_CSS = ROOT / "mielenosoitukset_fi/static/css/v2/auth.css"
WEBAUTHN_JS = ROOT / "mielenosoitukset_fi/static/js/webauthn.js"


def test_login_uses_shared_layout_and_conditional_passkey_contract(client):
    response = client.get("/users/auth/login")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    template = LOGIN_TEMPLATE.read_text(encoding="utf-8")
    webauthn = WEBAUTHN_JS.read_text(encoding="utf-8")

    assert 'class="auth-layout"' in html
    assert 'class="auth-intro"' in html
    assert '<main class="auth-wrapper">' not in template
    assert 'autocomplete="username webauthn"' in html
    assert "isConditionalMediationAvailable" in template
    assert "mediation: 'conditional'" in template
    assert "new AbortController()" in template
    assert "credentialOptions.mediation" in webauthn
    assert "credentialOptions.signal" in webauthn
    assert "innerHTML" not in template
    assert "document.createElement('style')" not in template
    assert "style=" not in template


def test_register_uses_grouped_accessible_shared_form_contract(client):
    response = client.get("/users/auth/register")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    template = REGISTER_TEMPLATE.read_text(encoding="utf-8")

    assert 'class="auth-layout"' in html
    assert '<main class="auth-wrapper">' not in template
    assert html.count('class="form-section"') == 2
    assert 'id="password-toggle-button"' in html
    assert 'id="password-confirm-toggle-button"' in html
    assert 'aria-pressed="false"' in html
    assert "crypto.getRandomValues" in template
    assert "Math.random" not in template
    assert "style=" not in template


def test_auth_styles_cover_theme_focus_and_responsive_states():
    css = AUTH_CSS.read_text(encoding="utf-8")

    assert "--auth-surface: light-dark(" in css
    assert ".auth-layout" in css
    assert ".auth-wrapper :is(" in css
    assert ":focus-visible" in css
    assert "@media (max-width: 760px)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css


@pytest.mark.parametrize(
    ("theme", "viewport"),
    [
        ("light", {"width": 1366, "height": 900}),
        ("dark", {"width": 390, "height": 844}),
    ],
)
@pytest.mark.parametrize("path", ["/users/auth/login", "/users/auth/register"])
def test_auth_pages_render_without_horizontal_overflow(
    live_server, browser_page, theme, viewport, path
):
    browser_page.set_viewport_size(viewport)
    browser_page.add_init_script(f"localStorage.setItem('theme', '{theme}')")
    browser_page.goto(f"{live_server}{path}", wait_until="domcontentloaded")

    assert browser_page.locator(".auth-layout").is_visible()
    assert browser_page.locator(".auth-intro").is_visible()
    assert theme in (browser_page.locator("html").get_attribute("class") or "")
    assert browser_page.evaluate(
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    )

    columns = browser_page.locator(".auth-layout").evaluate(
        "element => getComputedStyle(element).gridTemplateColumns"
    )
    if viewport["width"] > 760:
        assert " " in columns
    else:
        assert " " not in columns


def test_login_starts_conditional_passkey_mediation(live_server, browser_page):
    browser_page.add_init_script(
        """
        Object.defineProperty(window, 'PublicKeyCredential', {
          configurable: true,
          value: { isConditionalMediationAvailable: async () => true }
        });
        Object.defineProperty(navigator, 'credentials', {
          configurable: true,
          value: {
            get: (options) => {
              window.__conditionalCredentialOptions = options;
              return new Promise((resolve, reject) => {
                options.signal.addEventListener('abort', () => {
                  reject(new DOMException('Aborted', 'AbortError'));
                }, { once: true });
              });
            }
          }
        });
        """
    )
    browser_page.goto(f"{live_server}/users/auth/login", wait_until="domcontentloaded")
    browser_page.wait_for_function("window.__conditionalCredentialOptions !== undefined")

    assert browser_page.evaluate(
        "window.__conditionalCredentialOptions.mediation"
    ) == "conditional"
    assert browser_page.evaluate(
        "window.__conditionalCredentialOptions.signal instanceof AbortSignal"
    )
