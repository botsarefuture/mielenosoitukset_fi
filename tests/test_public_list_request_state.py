"""Shared public loader/controller evidence, with adversarial response order."""
from pathlib import Path
import pytest

SCRIPTS = Path('mielenosoitukset_fi/static/js')


@pytest.mark.parametrize('locale,label', [('en', 'Try again'), ('sv', 'Försök igen')])
def test_public_retry_uses_compiled_locale_catalog(locale, label):
    import gettext
    with Path(f'mielenosoitukset_fi/translations/{locale}/LC_MESSAGES/messages.mo').open('rb') as stream:
        assert gettext.GNUTranslations(stream).gettext('Yritä uudelleen') == label


def _loader_harness(page):
    page.set_content('''<div id="demos-grid"></div><div id="no-results"></div>
      <p id="listing-result-summary" data-format="Showing __START__–__END__ / __COUNT__" hidden></p>
      <div id="listing-load-error" hidden><button>Retry</button></div><button id="load-more-btn"></button>''')
    page.add_script_tag(path=str(SCRIPTS / 'demo-card-render.js'))
    page.evaluate('''() => {
      window.pending = [];
      window.fetch = (url, options) => new Promise(resolve => pending.push({url, options, resolve}));
      renderDemoCards = rows => {
        rows.forEach(row => {
          const node = document.createElement('div'); node.textContent = row.title;
          document.getElementById('demos-grid').append(node);
        }); return [];
      };
      getFriendsAttending = () => {};
      window.setup_grid_navigation = () => {};
      window.finish = (index, data, ok = true) => pending[index].resolve({ok, status: ok ? 200 : 503, json: async () => data});
    }''')


@pytest.mark.e2e
def test_public_loader_ignores_stale_search_and_counts_appended_results(browser_page):
    _loader_harness(browser_page)
    result = browser_page.evaluate('''async () => {
      const old = loadDemos(1, false, {search: 'old'});
      const latest = loadDemos(1, false, {search: 'latest'});
      finish(1, {results: [{title: 'Latest'}], page: 1, total_pages: 2, total: 2});
      await latest;
      finish(0, {results: [{title: 'Stale'}], page: 1, total_pages: 1, total: 99});
      await old;
      const afterSearch = document.getElementById('demos-grid').textContent;
      const append = loadDemos(2, true, {search: 'latest'});
      finish(2, {results: [{title: 'Next'}], page: 2, total_pages: 2, total: 2});
      await append;
      const beyond = loadDemos(3, true, {search: 'latest'});
      finish(3, {results: [], page: 3, total_pages: 2, total: 2}); await beyond;
      return {afterSearch, cards: document.getElementById('demos-grid').textContent,
        summary: document.getElementById('listing-result-summary').textContent,
        emptyDisplay: document.getElementById('no-results').style.display,
        aborted: pending[0].options.signal.aborted};
    }''')
    assert result == {'afterSearch': 'Latest', 'cards': 'LatestNext',
                      'summary': 'Showing 1–2 / 2', 'emptyDisplay': 'none', 'aborted': True}


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
def test_public_loader_http_failure_offers_retry_without_erasing_append(browser_page):
    _loader_harness(browser_page)
    browser_page.evaluate('''async () => {
      const first = loadDemos(1, false);
      finish(0, {results: [{title: 'Kept'}], page: 1, total_pages: 2, total: 2}); await first;
      const failed = loadDemos(2, true);
      finish(1, {}, false); await failed;
    }''')
    assert browser_page.locator('#listing-load-error').is_visible()
    assert browser_page.locator('#demos-grid').inner_text() == 'Kept'
    browser_page.locator('#listing-load-error button').click()
    assert browser_page.evaluate('''async () => {
      await loadDemos(2, true); return pending.length;
    }''') == 3  # the retry and Load more cannot append the same page twice
    browser_page.evaluate('''async () => {
      finish(2, {results: [{title: 'Retried'}], page: 2, total_pages: 2, total: 2});
      await new Promise(resolve => setTimeout(resolve, 0));
    }''')
    assert not browser_page.locator('#listing-load-error').is_visible()
    assert browser_page.locator('#demos-grid').inner_text() == 'Kept\nRetried'
    assert browser_page.locator('#listing-result-summary').inner_text() == 'Showing 1–2 / 2'


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
