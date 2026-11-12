from pathlib import Path
import json
import re

import pytest


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize('path', ['/demonstrations', '/city/Helsinki', '/tag/test-tag'])
@pytest.mark.parametrize('theme', ['light', 'dark'])
@pytest.mark.parametrize('width', [320, 360, 390, 1440])
@pytest.mark.parametrize('populated', [False, True])
def test_public_collection_page_fits_viewport_without_clipping(live_server, browser_page, tmp_path, path, theme, width, populated):
    browser_page.set_viewport_size({'width': width, 'height': 900})
    browser_page.add_init_script(f"localStorage.setItem('theme', '{theme}')")
    rows = [{'_id': '000000000000000000000001', 'title': 'Mielenosoitus' * 10,
        'date': '2099-01-01', 'start_time': '12:00', 'city': 'Helsinki',
        'address': 'Kokoontumispaikka' * 6, 'tags': ['yhteiskunnallinenmielenosoitus' * 3]}] if populated else []
    browser_page.route('**/api/demonstrations?*', lambda route: route.fulfill(
        content_type='application/json', body=json.dumps({'page': 1, 'total_pages': 1, 'total': len(rows), 'results': rows})))
    browser_page.goto(f'{live_server}{path}', wait_until='domcontentloaded')
    browser_page.locator('#listing-result-summary').wait_for(state='visible')
    geometry = browser_page.evaluate('''() => {
      const viewport = document.documentElement.clientWidth;
      return {viewport, width: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth),
        outside: [...document.body.querySelectorAll('*')].map(element => {
          const rect = element.getBoundingClientRect();
          return {tag: element.tagName, classes: element.className?.toString(),
            width: Math.round(rect.width), right: Math.round(rect.right),
            boxSizing: getComputedStyle(element).boxSizing,
            padding: getComputedStyle(element).padding, minWidth: getComputedStyle(element).minWidth};
        }).filter(rect => rect.width > 0 && rect.right > viewport + 1).slice(-12)};
    }''')
    assert geometry['width'] <= geometry['viewport'] + 1, json.dumps(geometry, indent=2)
    if populated:
        cards = browser_page.locator('.demo-card[data-demo-id]')
        assert cards.count() == len(rows)
        card = cards.first
        assert card.locator('.demo-card-title').inner_text() == rows[0]['title']
        assert rows[0]['address'] in card.locator('.demo-card-address').inner_text()
        assert card.locator('.demo-card-tag').inner_text() == '#' + rows[0]['tags'][0]
        for selector in ['.demo-card-title', '.demo-card-address', '.demo-card-tag']:
            text = card.locator(selector)
            assert text.evaluate('element => element.scrollWidth <= element.clientWidth + 1'), selector
    footer = browser_page.locator('.public-site-footer')
    assert footer.evaluate('element => getComputedStyle(element).backgroundColor') == (
        'rgb(255, 255, 255)' if theme == 'light' else 'rgb(32, 37, 45)')
    footer.scroll_into_view_if_needed()
    assert footer.evaluate('element => getComputedStyle(element).overflowX') == 'visible'
    assert footer.evaluate('element => element.scrollWidth <= element.clientWidth + 1')
    for link in footer.locator('a').all():
        rect = link.bounding_box()
        assert rect['x'] >= -1 and rect['x'] + rect['width'] <= width + 1
    links = footer.locator('a')
    links.last.focus()
    browser_page.keyboard.press('Shift+Tab')
    focused = links.nth(links.count() - 2)
    assert focused.evaluate('element => element === document.activeElement')
    assert focused.evaluate('element => getComputedStyle(element).outlineStyle') != 'none'
    if path == '/demonstrations' and width == 390:
        state = 'populated' if populated else 'empty'
        footer.screenshot(path=str(tmp_path / f'footer-{theme}-{width}-{state}.png'))


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize('view', ['home', 'organization', 'organization-long'])
@pytest.mark.parametrize('theme', ['light', 'dark'])
@pytest.mark.parametrize('width', [320, 360, 390, 1440])
def test_home_and_organization_layout_preserves_content(live_server, browser_page, db, seeded_data, tmp_path, view, theme, width):
    if view == 'organization-long':
        db.organizations.update_one({'_id': seeded_data['org_id']}, {'$set': {
            'name': 'Yhdenvertaisuusverkosto' * 4,
            'description': 'Yhteistä toimintaa ja paikallista vaikuttamista. ' * 4,
        }})
    path = '/' if view == 'home' else f"/organization/{seeded_data['org_id']}"
    browser_page.set_viewport_size({'width': width, 'height': 1000})
    browser_page.add_init_script(f"localStorage.setItem('theme', '{theme}')")
    browser_page.route('**/api/demonstrations?*', lambda route: route.fulfill(
        content_type='application/json', body='{"page":1,"total_pages":1,"total":0,"results":[]}'))
    browser_page.goto(f'{live_server}{path}', wait_until='domcontentloaded')
    hero = browser_page.locator('.site-hero')
    assert theme in (browser_page.locator('html').get_attribute('class') or '').split()
    assert hero.count() == 1
    title = hero.locator('h1')
    assert title.is_visible()
    assert title.inner_text().strip()
    if width <= 720:
        # The shared responsive scale must win over legacy container heading resets.
        expected_size = max(24, min(width * 0.07, 39.2))
        assert title.evaluate('element => parseFloat(getComputedStyle(element).fontSize)') == pytest.approx(expected_size, abs=0.1)
    sizes = browser_page.evaluate('''() => ({
      viewport: document.documentElement.clientWidth,
      width: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)})''')
    assert sizes['width'] <= sizes['viewport'] + 1, sizes
    assert title.evaluate('element => element.scrollWidth <= element.clientWidth + 1')
    assert title.evaluate('element => getComputedStyle(element).color') == 'rgb(255, 255, 255)'
    assert hero.evaluate('element => element.scrollWidth <= element.clientWidth + 1')
    bounds = hero.bounding_box()
    assert bounds['x'] >= -1 and bounds['x'] + bounds['width'] <= width + 1
    assert abs(bounds['x'] - (width - bounds['x'] - bounds['width'])) <= 2
    links = hero.locator('a[href]')
    if view == 'home':
        assert links.count() == 3
    for link in links.all():
        box = link.bounding_box()
        assert box['x'] >= bounds['x'] - 1 and box['x'] + box['width'] <= bounds['x'] + bounds['width'] + 1
        assert link.evaluate('element => element.scrollWidth <= element.clientWidth + 1')
    if view == 'organization-long':
        assert title.inner_text() == 'Yhdenvertaisuusverkosto' * 4
        assert hero.locator('.org-desc').inner_text() == ('Yhteistä toimintaa ja paikallista vaikuttamista. ' * 4).strip()
    if width in [320, 390, 1440]:
        hero.screenshot(path=str(tmp_path / f'hero-{view}-{theme}-{width}.png'), animations='disabled')


def test_shared_information_cards_have_mobile_shrink_contract():
    css = Path("mielenosoitukset_fi/static/css/v2/gen.css").read_text(
        encoding="utf-8"
    )

    assert re.search(r'\.container-main-content\s*\{[^}]*box-sizing:\s*border-box\s*;', css)
    assert re.search(r'\.cards-grid\s*>\s*\*\s*\{[^}]*min-width:\s*0\s*;', css)
    assert re.search(r'\.section-card p\s*(?:,[^{}]+)?\{[^}]*overflow-wrap:\s*anywhere\s*;', css)


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize("viewport_width", [320, 360, 390])
def test_information_cards_fit_portrait_viewport(
    live_server, browser_page, viewport_width
):
    browser_page.set_viewport_size({"width": viewport_width, "height": 800})
    browser_page.goto(f"{live_server}/info", wait_until="domcontentloaded")

    contract = browser_page.evaluate(
        """() => ({
            viewport: document.documentElement.clientWidth,
            documentWidth: document.documentElement.scrollWidth,
            cards: [...document.querySelectorAll('.section-card')].map(card => {
                const rect = card.getBoundingClientRect();
                return {
                    left: rect.left,
                    right: rect.right,
                    contentOverflow: card.scrollWidth - card.clientWidth,
                };
            }),
        })"""
    )

    assert contract["documentWidth"] <= contract["viewport"] + 1
    assert contract["cards"]
    for card in contract["cards"]:
        assert card["left"] >= -1
        assert card["right"] <= contract["viewport"] + 1
        assert card["contentOverflow"] <= 1
