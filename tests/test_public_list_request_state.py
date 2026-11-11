"""Shared public loader/controller evidence, with adversarial response order."""
from pathlib import Path
import pytest

SCRIPTS = Path('mielenosoitukset_fi/static/js')


@pytest.mark.parametrize('locale,label', [('en', 'Try again'), ('sv', 'Försök igen')])
def test_public_retry_uses_compiled_locale_catalog(locale, label):
    import gettext
    with Path(f'mielenosoitukset_fi/translations/{locale}/LC_MESSAGES/messages.mo').open('rb') as stream:
        assert gettext.GNUTranslations(stream).gettext('Yritä uudelleen') == label


@pytest.mark.e2e
def test_public_controller_old_finally_cannot_unlock_new_search(browser_page):
    browser_page.set_content('<button id="more">More</button>')
    browser_page.add_script_tag(path=str(SCRIPTS / 'user-pagination.js'))
    result = browser_page.evaluate('''async () => {
      const pending = [];
      const button = document.getElementById('more');
      const controller = UserPagination.createLoadMoreController({button,
        loadPage: page => new Promise(resolve => pending.push({page, resolve}))});
      controller.setState(1, 3);
      const old = controller.loadNext();
      const replacement = controller.reload();
      pending[0].resolve({page: 2, total_pages: 9}); await old;
      const locked = button.disabled;
      await controller.loadNext();
      const count = pending.length;
      pending[1].resolve({page: 1, total_pages: 2}); await replacement;
      return {locked, count, page: controller.currentPage, pages: controller.totalPages,
        disabled: button.disabled, requested: pending.map(p => p.page)};
    }''')
    assert result == {'locked': True, 'count': 2, 'page': 1, 'pages': 2,
                      'disabled': False, 'requested': [2, 1]}


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize('path', ['/demonstrations', '/city/Helsinki', '/tag/test-tag'])
@pytest.mark.parametrize('theme,width', [('light', 1440), ('dark', 1440), ('light', 390), ('dark', 390)])
def test_public_listing_summary_is_shared_responsive_and_keyboard_operable(live_server, browser_page, path, theme, width):
    # Exercise the manual keyboard fallback used by data-saving clients.
    browser_page.add_init_script("Object.defineProperty(navigator, 'connection', {value: {saveData: true}})")
    import json
    from urllib.parse import parse_qs, urlsplit
    browser_page.set_viewport_size({'width': width, 'height': 1000})
    browser_page.add_init_script(f"localStorage.setItem('theme', '{theme}')")

    def serve_page(route):
        page = int(parse_qs(urlsplit(route.request.url).query)['page'][0])
        titles = ['First', 'Second'] if page == 1 else ['Third']
        route.fulfill(content_type='application/json', body=json.dumps({
            'page': page, 'total_pages': 2, 'total': 3,
            'results': [{'_id': str(index), 'title': title, 'date': '2099-01-01',
                         'start_time': '12:00', 'city': 'Helsinki', 'tags': []}
                        for index, title in enumerate(titles)],
        }))
    browser_page.route('**/api/demonstrations?*', serve_page)
    errors = []
    browser_page.on('pageerror', lambda error: errors.append(error.stack))
    browser_page.goto(f'{live_server}{path}', wait_until='domcontentloaded')
    browser_page.wait_for_function("document.getElementById('listing-result-summary').textContent.includes('1–2')")
    summary = browser_page.locator('#listing-result-summary')
    assert summary.get_attribute('role') == 'status'
    assert summary.get_attribute('aria-live') == 'polite'
    assert summary.inner_text() == 'Näytetään 1–2 / 3 mielenosoituksesta'
    browser_page.locator('#load-more-btn').focus()
    browser_page.keyboard.press('Enter')
    browser_page.wait_for_function("document.getElementById('listing-result-summary').textContent.includes('1–3')")
    assert summary.inner_text() == 'Näytetään 1–3 / 3 mielenosoituksesta'
    browser_page.locator('#load-more-btn').wait_for(state='hidden', timeout=5000)
    geometry = summary.evaluate('''element => {
      const rect = element.getBoundingClientRect();
      const css = getComputedStyle(element);
      return {left: rect.left, right: rect.right, color: css.color, width: innerWidth};
    }''')
    assert geometry['left'] >= 0 and geometry['right'] <= geometry['width'] + 1
    assert geometry['color'] != 'rgba(0, 0, 0, 0)'
    assert browser_page.locator('html').evaluate('(element, theme) => element.classList.contains(theme)', theme)
    assert not errors
    if path == '/demonstrations':
        browser_page.screenshot(path=f'/tmp/moso-list-summary-{theme}-{width}.png', full_page=True)
