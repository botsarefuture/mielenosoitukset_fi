"""Automatic bounded public lists: real renderer/controller, isolated API data."""
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize('path', ['/demonstrations', '/city/Helsinki', '/tag/window-test'])
@pytest.mark.parametrize('theme,width', [('light', 1440), ('dark', 390)])
def test_automatic_public_lists_bound_dom_and_restore_discarded_pages(live_server, browser_page, path, theme, width):
    browser_page.set_viewport_size({'width': width, 'height': 900})
    browser_page.add_init_script(f"localStorage.setItem('theme', '{theme}')")
    requested = []

    def serve(route):
        query = parse_qs(urlsplit(route.request.url).query)
        page = int(query['page'][0])
        size = int(query['per_page'][0])
        requested.append(page)
        route.fulfill(content_type='application/json', body=json.dumps({
            'page': page, 'per_page': size, 'total_pages': 30, 'total': size * 30,
            'result_start': (page - 1) * size + 1, 'result_end': page * size,
            'results': [{'_id': f'{page}-{index}', 'title': f'Page {page} event {index}',
                         'date': '2099-01-01', 'start_time': '12:00', 'city': 'Helsinki', 'tags': []}
                        for index in range(size)],
        }))

    errors = []
    browser_page.on('pageerror', lambda error: errors.append(str(error)))
    browser_page.route('**/api/demonstrations?*', serve)
    browser_page.goto(f'{live_server}{path}', wait_until='domcontentloaded')
    browser_page.wait_for_function('window.publicListWindow?.last === 1')
    for target in range(2, 11):
        browser_page.evaluate("""() => { const host=publicListWindow.scrollHost;
          host.scrollTo({top:document.getElementById('load-more-btn').getBoundingClientRect().top
            +(host===window?scrollY:host.scrollTop)-publicListWindow.viewport().bottom+100,behavior:'instant'}); }""")
        try:
            browser_page.wait_for_function('(target) => window.publicListWindow.last >= target', arg=target, timeout=5000)
        except Exception:
            print('Automatic loading state', target, requested, errors, browser_page.evaluate('''() => ({
              first:publicListWindow.first,last:publicListWindow.last,y:scrollY,height:innerHeight,
              button:document.getElementById('load-more-btn').getBoundingClientRect().toJSON(),
              hidden:document.getElementById('load-more-btn').hidden,
              disabled:document.getElementById('load-more-btn').disabled,
              focus:document.activeElement.id, scrolling:document.scrollingElement.tagName,
              root:document.scrollingElement.scrollHeight, body:document.body.scrollHeight,
              ancestors:(()=>{let e=document.getElementById('demos-grid'),r=[];while(e){r.push([e.tagName,e.id,e.scrollHeight,e.clientHeight,getComputedStyle(e).overflowY]);e=e.parentElement;}return r;})()})'''))
            raise
        assert browser_page.locator('.public-list-page').count() <= 5
        assert browser_page.locator('#demos-grid .demo-card').count() <= 60
    first = browser_page.evaluate('publicListWindow.first')
    assert first >= 6
    assert not browser_page.locator('[data-list-page="1"]').count()
    # Scroll back without pressing Previous; a discarded page is re-fetched.
    browser_page.evaluate("""() => { const host=publicListWindow.scrollHost;
      host.scrollTo({top:document.getElementById('load-previous-btn').getBoundingClientRect().top
        +(host===window?scrollY:host.scrollTop)-publicListWindow.viewport().top,behavior:'instant'}); }""")
    browser_page.wait_for_function('(first) => publicListWindow.first < first', arg=first)
    assert first - 1 in requested
    assert browser_page.locator('.public-list-page').count() == 5
    assert browser_page.locator('#demos-grid .demo-card').count() == 60
    retained = browser_page.evaluate('({first: publicListWindow.first, last: publicListWindow.last})')
    assert retained['last'] - retained['first'] == 4
    assert not errors
    # Rendered cards have the same grid on mobile and desktop, no page-width leak.
    assert browser_page.locator('.public-list-page').first.evaluate('(node) => node.getBoundingClientRect().width <= innerWidth')
    if path == '/demonstrations':
        browser_page.screenshot(path=f'/tmp/moso-windowed-{theme}-{width}.png')


@pytest.mark.e2e
def test_delayed_append_preserves_new_focus_and_cannot_restore_old_filter_pages(browser_page):
    browser_page.set_viewport_size({'width': 1280, 'height': 900})
    browser_page.set_content('''<style>.public-list-page{height:600px;overflow-anchor:none}</style>
      <div id="demos-grid"></div><div id="no-results"></div>
      <p id="listing-result-summary" data-format="__START__–__END__ / __COUNT__"></p>
      <div id="listing-load-error" hidden><button>Retry</button></div>''')
    scripts = Path('mielenosoitukset_fi/static/js')
    browser_page.add_script_tag(path=str(scripts / 'user-pagination.js'))
    browser_page.add_script_tag(path=str(scripts / 'demo-card-render.js'))
    result = browser_page.evaluate('''async () => {
      const pending=[];
      window.fetch=(url,options)=>new Promise(resolve=>pending.push({options,resolve}));
      getFriendsAttending=()=>{};
      renderDemoCards=(rows,options)=>rows.map(row=>{
        const link=document.createElement('a');link.href='#';link.textContent=row.title;
        options.container.append(link);return link;
      });
      window.publicListWindow=UserPagination.createPageWindow(document.getElementById('demos-grid'));
      const finish=(index,page,title)=>pending[index].resolve({ok:true,json:async()=>({
        page,per_page:1,total_pages:20,total:20,result_start:page,result_end:page,
        results:[{title}]})});
      for(let page=1;page<=5;page++){
        scrollTo(0,document.body.scrollHeight);
        const request=loadDemos(page,page!==1);finish(page-1,page,`Page ${page}`);await request;
      }
      scrollTo(0,document.body.scrollHeight);
      const delayed=loadDemos(6,true);
      const focus=document.querySelector('[data-list-page="1"] a');focus.focus({preventScroll:true});
      finish(5,6,'Must not evict focus');const blocked=await delayed;
      const preserved=focus.isConnected && document.activeElement===focus && publicListWindow.first===1;
      focus.blur();
      const old=loadDemos(6,true);
      const search=loadDemos(1,false,{search:'new'});
      finish(7,1,'New filter');await search;
      finish(6,6,'Stale old filter');await old;
      return {preserved,deferred:blocked?.deferred,aborted:pending[6].options.signal.aborted,
        pages:document.querySelectorAll('.public-list-page').length,
        text:document.getElementById('demos-grid').textContent,
        busy:document.getElementById('demos-grid').getAttribute('aria-busy')};
    }''')
    assert result == {'preserved': True, 'deferred': True, 'aborted': True,
                      'pages': 1, 'text': 'New filter', 'busy': 'false'}


@pytest.mark.e2e
def test_window_does_not_discard_keyboard_focus_and_preserves_scroll_anchor(browser_page):
    browser_page.set_content('<style>.public-list-page{height:600px;overflow-anchor:none} #demos-grid{overflow-anchor:none}</style><div id="demos-grid"></div>')
    browser_page.add_script_tag(path=str(Path('mielenosoitukset_fi/static/js/user-pagination.js')))
    result = browser_page.evaluate('''() => {
      const win = UserPagination.createPageWindow(document.getElementById('demos-grid'));
      const mount = page => win.mount({page, per_page:1, result_start:page, result_end:page,
        results:[{}]}, node => { const link = document.createElement('a');
          link.href = '#'; link.textContent = page; node.append(link); return [link]; });
      for(let page=1;page<=5;page++) mount(page);
      const visibleBlocked = !win.canExtend();
      const manualAllowed = win.canExtend(false,true);
      const focused = document.querySelector('[data-list-page="1"] a');
      focused.focus({preventScroll:true}); scrollTo(0, 2400);
      const pinned = win.canExtend();
      const manualPinned = win.canExtend(false,true);
      focused.blur();
      const allowed = win.canExtend();
      const anchor = document.querySelector('[data-list-page="5"]');
      const before = anchor.getBoundingClientRect().top;
      mount(6);
      return {pinned, manualPinned, visibleBlocked, manualAllowed, allowed, before, after:anchor.getBoundingClientRect().top,
        count:document.querySelectorAll('.public-list-page').length, first:win.first};
    }''')
    assert result['pinned'] is False and result['allowed'] is True
    assert result['manualPinned'] is False
    assert result['visibleBlocked'] is True and result['manualAllowed'] is True
    assert result['count'] == 5 and result['first'] == 2
    assert abs(result['before'] - result['after']) <= 1


@pytest.mark.e2e
def test_automatic_requests_are_single_flight_and_failure_never_loops(browser_page):
    browser_page.set_viewport_size({'width': 1280, 'height': 900})
    browser_page.set_content('''<div style="height:3000px"></div><div id="demos-grid"></div>
      <button id="load-previous-btn" hidden>Previous</button><button id="more">More</button>''')
    browser_page.add_script_tag(path=str(Path('mielenosoitukset_fi/static/js/user-pagination.js')))
    browser_page.evaluate('''() => {
      window.pending=[];
      window.controller=UserPagination.createLoadMoreController({windowed:true,
        button:document.getElementById('more'), loadPage:page=>new Promise(resolve=>pending.push({page,resolve}))});
      controller.setState(1,10);
      scrollTo(0, document.body.scrollHeight);
    }''')
    browser_page.wait_for_function('pending.length === 1')
    browser_page.evaluate('''() => {
      for(let index=0;index<30;index++) dispatchEvent(new Event('scroll'));
      controller.loadNext(); controller.loadNext();
    }''')
    assert browser_page.evaluate('pending.length') == 1
    browser_page.evaluate('pending[0].resolve(null)')
    browser_page.wait_for_function('!document.getElementById("more").disabled')
    browser_page.evaluate('''() => { scrollTo(0,0); scrollTo(0, document.body.scrollHeight); }''')
    # Flush scheduled frames rather than an arbitrary long sleep.
    browser_page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
    assert browser_page.evaluate('pending.length') == 1
    browser_page.locator('#more').click()
    browser_page.wait_for_function('pending.length === 2')
    assert browser_page.evaluate('pending[1].page') == 2
    browser_page.evaluate('controller.destroy(); pending[1].resolve({page:2,total_pages:10})')
    browser_page.evaluate('() => new Promise(resolve => requestAnimationFrame(resolve))')
    assert browser_page.evaluate('controller.currentPage') == 1


@pytest.mark.e2e
def test_successful_retry_resumes_automatic_loading_without_another_scroll(browser_page):
    browser_page.set_viewport_size({'width': 1280, 'height': 900})
    browser_page.set_content('''<div style="height:3000px"></div><div id="demos-grid"></div>
      <button id="load-previous-btn" hidden>Previous</button><button id="more">More</button>''')
    browser_page.add_script_tag(path=str(Path('mielenosoitukset_fi/static/js/user-pagination.js')))
    browser_page.evaluate('''() => {
      window.pending=[];
      window.controller=UserPagination.createLoadMoreController({windowed:true,
        button:document.getElementById('more'),loadPage:page=>new Promise(resolve=>pending.push({page,resolve}))});
      controller.setState(1,10);scrollTo(0,document.body.scrollHeight);
    }''')
    browser_page.wait_for_function('pending.length === 1')
    browser_page.evaluate('pending[0].resolve(null)')
    browser_page.wait_for_function('!document.getElementById("more").disabled')
    browser_page.evaluate('() => new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
    assert browser_page.evaluate('pending.length') == 1
    # Actual retry loader updates controller state, then invokes resumeAuto.
    position = browser_page.evaluate('scrollY')
    browser_page.evaluate('controller.setState(2,10);controller.resumeAuto()')
    browser_page.wait_for_function('pending.length === 2')
    assert browser_page.evaluate('pending[1].page') == 3
    assert browser_page.evaluate('scrollY') == position
    browser_page.evaluate('pending[1].resolve({page:3,total_pages:3})')
    browser_page.wait_for_function('controller.currentPage === 3')
    assert browser_page.evaluate('pending.length') == 2
    browser_page.evaluate('controller.destroy()')
