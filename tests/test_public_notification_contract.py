from pathlib import Path


TEMPLATE_PATH = Path("mielenosoitukset_fi/templates/header.html")
SCRIPT_PATH = Path("mielenosoitukset_fi/static/js/public-notifications.js")
STYLESHEET_PATH = Path("mielenosoitukset_fi/static/css/user-workspace.css")


def test_notification_popover_uses_accessible_shared_markup():
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    assert 'aria-controls="notif-panel"' in template
    assert 'role="dialog"' in template
    assert 'aria-labelledby="notif-panel-title"' in template
    assert 'aria-live="polite"' in template
    assert 'aria-busy="true"' in template
    assert 'style="max-height:360px;overflow-y:auto;"' not in template
    assert "public-notifications.js" in template


def test_notification_payload_is_rendered_without_html_interpolation():
    script = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "innerHTML" not in script
    assert "insertAdjacentHTML" not in script
    assert "message.textContent" in script
    assert "timestamp.textContent" in script
    assert "safeNotificationHref" in script
    assert 'url.origin !== window.location.origin' in script
    assert 'value.startsWith("/")' in script


def test_notification_states_use_shared_product_tokens():
    stylesheet = STYLESHEET_PATH.read_text(encoding="utf-8")

    assert ".notif-state--error" in stylesheet
    assert ".notif-item.is-unread" in stylesheet
    assert ".notif-item__link:focus-visible" in stylesheet
    assert "var(--admin-workspace-surface)" in stylesheet
    assert "var(--admin-workspace-border)" in stylesheet
    assert "@media (prefers-reduced-motion: reduce)" in stylesheet
