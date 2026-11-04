"""Behavior across the Flask account boundary and React header ownership."""
import json
import re

import pytest
from playwright.sync_api import expect


def header_props(response):
    match = re.search(r'<script id="site-header-props" type="application/json">(.*?)</script>', response.get_data(as_text=True), re.S)
    assert match
    return json.loads(match.group(1))


def test_header_account_permissions_and_escaped_props(client, user_client, admin_client, db, seeded_data):
    guest = header_props(client.get('/info'))
    member = header_props(user_client.get('/info'))
    admin = header_props(admin_client.get('/info'))
    assert guest['account'] is None
    assert any('login' in link['href'] for link in guest['links'])
    assert not any('/admin' in link['href'] for link in member['account']['links'])
    assert any('/admin' in link['href'] for link in admin['account']['links'])
    attack = '</script><script>window.headerInjected=true</script>'
    db.users.update_one({'_id': seeded_data['user_id']}, {'$set': {'displayname': attack}})
    response = user_client.get('/info')
    assert attack not in response.get_data(as_text=True)
    assert header_props(response)['account']['name'] == attack


def test_header_language_links_preserve_query_and_public_locale_gate(app, client):
    app.config['BABEL_PUBLIC_LOCALES'] = ['fi', 'en', 'sv']
    props = header_props(client.get('/info?occurrence=example&view=classic'))
    assert [language['code'] for language in props['languages']] == ['fi', 'en', 'sv']
    from urllib.parse import parse_qs, urlsplit
    for language in props['languages']:
        assert parse_qs(urlsplit(language['href']).query)['next'] == ['/info?occurrence=example&view=classic']


def authenticate(page, client, base):
    page.context.add_cookies([{'name': 'session', 'value': client.get_cookie('session').value, 'url': base}])


@pytest.mark.e2e
@pytest.mark.integration
def test_header_user_menu_keyboard_and_sticky_navigation(live_server, browser_page, user_client):
    authenticate(browser_page, user_client, live_server)
    browser_page.goto(live_server + '/info', wait_until='domcontentloaded')
    browser_page.set_viewport_size({'width': 1440, 'height': 500})
    button = browser_page.locator('#user-toggle-btn')
    button.focus()
    browser_page.keyboard.press('ArrowDown')
    expect(button).to_have_attribute('aria-expanded', 'true')
    expect(browser_page.locator('#user-dropdown-menu a').first).to_be_focused()
    browser_page.keyboard.press('End')
    expect(browser_page.locator('#user-dropdown-menu a').last).to_be_focused()
    browser_page.keyboard.press('Escape')
    expect(button).to_have_attribute('aria-expanded', 'false')
    expect(button).to_be_focused()
    expect(browser_page.locator('#user-dropdown-menu')).to_be_hidden()
    browser_page.mouse.wheel(0, 500)
    browser_page.wait_for_function('scrollY > 100 || document.body.scrollTop > 100')
    assert abs(browser_page.locator('.public-main-nav').bounding_box()['y']) <= 1


@pytest.mark.e2e
@pytest.mark.integration
def test_header_notifications_use_existing_api_and_render_untrusted_text_safely(live_server, browser_page, user_client, db, seeded_data):
    authenticate(browser_page, user_client, live_server)
    db.notifications.update_one({'user_id': seeded_data['user_id']}, {'$set': {
        'type': 'friend_request', 'payload': {'sender_name': '<img src=x onerror=alert(1)>'},
        'link': 'https://example.test/external',
    }})
    browser_page.goto(live_server + '/info', wait_until='domcontentloaded')
    browser_page.locator('#notif-btn').click()
    expect(browser_page.locator('.notif-item__message')).to_contain_text('<img src=x onerror=alert(1)>')
    assert browser_page.locator('#notif-list img').count() == 0
    expect(browser_page.locator('.notif-item__link')).to_have_attribute('href', '#')
    browser_page.locator('#mark-read-btn').click()
    expect(browser_page.locator('.notif-item')).not_to_have_class(re.compile('is-unread'))
    assert db.notifications.find_one({'user_id': seeded_data['user_id']})['read'] is True
    browser_page.locator('#notif-btn').focus()
    browser_page.keyboard.press('Escape')
    expect(browser_page.locator('#notif-panel')).to_have_attribute('aria-hidden', 'true')
    expect(browser_page.locator('#notif-btn')).to_be_focused()


@pytest.mark.e2e
@pytest.mark.integration
def test_header_notification_errors_can_retry_without_false_mark_read(live_server, browser_page, user_client):
    authenticate(browser_page, user_client, live_server)
    status = {'fail': True}
    def notifications(route):
        route.fulfill(status=503 if status['fail'] else 200, content_type='application/json', body='[]')
    browser_page.route('**/api/notifications/', notifications)
    browser_page.goto(live_server + '/info', wait_until='domcontentloaded')
    button = browser_page.locator('#notif-btn')
    button.click()
    expect(browser_page.locator('#notif-list [role="alert"]')).to_be_visible()
    button.click()
    status['fail'] = False
    button.click()
    expect(browser_page.locator('#notif-list [role="status"]')).to_have_text('Ei ilmoituksia')
    expect(browser_page.locator('#notif-list')).to_have_attribute('aria-busy', 'false')


@pytest.mark.e2e
@pytest.mark.integration
def test_failed_header_module_keeps_mobile_and_account_navigation(live_server, browser_page, user_client):
    authenticate(browser_page, user_client, live_server)
    browser_page.set_viewport_size({'width': 390, 'height': 900})
    browser_page.route('**/frontend/assets/header-*.js', lambda route: route.abort())
    browser_page.goto(live_server + '/info', wait_until='networkidle')
    browser_page.locator('.header-fallback-toggle').click()
    navigation = browser_page.locator('.header-fallback-mobile .nav-list')
    expect(navigation).to_be_visible()
    expect(navigation.locator('a[href="/demonstrations"]')).to_be_visible()
    expect(navigation.locator('.dropdown-menu a').last).to_be_visible()
    assert navigation.get_attribute('inert') is None
    assert browser_page.locator('.public-header-ready').count() == 0


@pytest.mark.e2e
@pytest.mark.integration
def test_header_theme_state_tracks_existing_page_controls(live_server, browser_page):
    browser_page.add_init_script("localStorage.setItem('theme', 'light')")
    browser_page.goto(live_server + '/info', wait_until='networkidle')
    button = browser_page.locator('.theme-toggle')
    expect(button).to_have_attribute('aria-pressed', 'false')
    expect(button.locator('.header-theme-icon')).to_have_class(re.compile('fa-moon'))
    browser_page.evaluate('toggleDarkMode()')
    expect(button).to_have_attribute('aria-pressed', 'true')
    expect(button.locator('.header-theme-icon')).to_have_class(re.compile('fa-sun'))
    button.click()
    expect(button).to_have_attribute('aria-pressed', 'false')
    assert browser_page.evaluate("localStorage.getItem('theme')") == 'light'


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize('width', [390, 1440])
def test_header_mark_read_failure_preserves_unread_notification(live_server, browser_page, user_client, db, seeded_data, width):
    authenticate(browser_page, user_client, live_server)
    browser_page.set_viewport_size({'width': width, 'height': 900})
    browser_page.route('**/api/notifications/mark-read', lambda route: route.fulfill(status=503))
    browser_page.goto(live_server + '/info', wait_until='domcontentloaded')
    if width == 390:
        browser_page.locator('#mobile-menu-toggle').click()
    browser_page.locator('#notif-btn').click()
    expect(browser_page.locator('.notif-item.is-unread')).to_be_visible()
    browser_page.locator('#mark-read-btn').click()
    expect(browser_page.locator('#notif-panel [role="alert"]')).to_have_text('Ilmoituksia ei voitu merkitä luetuiksi.')
    expect(browser_page.locator('#notif-btn .notif-badge')).to_have_text('1')
    expect(browser_page.locator('#mark-read-btn')).to_be_enabled()
    assert db.notifications.find_one({'user_id': seeded_data['user_id']})['read'] is False
    browser_page.locator('#notif-btn').click()
    expect(browser_page.locator('#notif-panel')).to_have_attribute('aria-hidden', 'true')
