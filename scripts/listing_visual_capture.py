"""Local pytest capture plugin used by scripts/verify_react_listings.py.

It renders the real Flask application with disposable test fixtures. It is not
loaded by the normal test suite and never supplies a visual acceptance verdict.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
from urllib.parse import parse_qs, urlparse

from bson import ObjectId
import pytest

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_HOSTS = {
    "localhost", "127.0.0.1", "cdn2.mielenosoitukset.fi",
    "fonts.googleapis.com", "fonts.gstatic.com", "cdn.socket.io",
    "cdnjs.cloudflare.com", "a.tile.openstreetmap.org", "b.tile.openstreetmap.org", "c.tile.openstreetmap.org",
}
IMAGE_FIELDS = ("cover_picture", "cover_image", "preview_image", "img", "image_url")
PHOTO = "/static/kampanja/og-banner.png"


def source_inputs() -> dict:
    """Record the actual checkout and dirty inputs, including untracked files."""
    def git(*args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()

    changed = set(filter(None, git("diff", "--name-only", "-z", "HEAD").split("\0")))
    try:
        branch_changes = git("diff", "--name-only", "-z", "origin/main...HEAD")
    except subprocess.CalledProcessError as error:
        raise RuntimeError("Capture needs origin/main to record branch changes; fetch that base ref first.") from error
    changed.update(filter(None, branch_changes.split("\0")))
    changed.update(filter(None, git("ls-files", "--others", "--exclude-standard", "-z").split("\0")))
    changed.update({
        "tests/conftest.py", "config.py", "mielenosoitukset_fi/app.py",
        "mielenosoitukset_fi/basic_routes.py", "mielenosoitukset_fi/api/routes.py",
        "scripts/listing_visual_capture.py", "scripts/verify_react_listings.py",
        "mielenosoitukset_fi/templates/base.html",
        "mielenosoitukset_fi/templates/_layouts/demonstration-list.html",
        "mielenosoitukset_fi/templates/_partials/demonstration-listing.html",
        "mielenosoitukset_fi/templates/organizations/details.html",
        "mielenosoitukset_fi/templates/pride-nakyvaksi/index.html",
        "mielenosoitukset_fi/static/leaflet/leaflet.js", "mielenosoitukset_fi/static/leaflet/leaflet.css",
        "mielenosoitukset_fi/static/css/user-workspace.css",
        "mielenosoitukset_fi/static/css/product-tokens.css",
        "mielenosoitukset_fi/static/js/user-pagination.js",
        "mielenosoitukset_fi/static/js/public-date-range.js",
        "mielenosoitukset_fi/static/js/public-city-autocomplete.js",
        "mielenosoitukset_fi/static/kampanja/og-banner.png",
    })
    changed.update(filter(None, git("ls-files", "-z", "--", "frontend", "mielenosoitukset_fi/static/frontend").split("\0")))
    hashes = {}
    for name in sorted(changed):
        path = ROOT / name
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "DELETED"
    return {"head": git("rev-parse", "HEAD"), "worktree": str(ROOT), "files": hashes,
            "sha256": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()}


def capture(item) -> None:
    output = Path(os.environ["MOSO_LIST_CAPTURE_DIR"]).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    stage = os.environ.get("MOSO_LIST_CAPTURE_STAGE", "final")
    scenario = os.environ.get("MOSO_LIST_CAPTURE_SCENARIO", "standard")
    if stage not in {"before", "final"}:
        raise ValueError("Capture stage must be before or final")
    request = item._request
    client = request.getfixturevalue("client")
    db = request.getfixturevalue("db")
    seed = request.getfixturevalue("seeded_data")
    base = request.getfixturevalue("live_server")
    browser = request.getfixturevalue("playwright_browser")
    app = client.application
    images, errors, failed, image_hashes, image_states = [], [], [], {}, {}
    inputs_before = source_inputs()

    record = db.demonstrations.find_one({"_id": seed["demo_id"]})
    if scenario in {"missing-times", "continuous-grid", "organization", "pride"}:
        db.demonstrations.delete_many({})
        db.recurring_demonstrations.delete_many({})
    for index in range(72 if scenario in {"missing-times", "continuous-grid", "organization", "pride"} else 15):
        row = deepcopy(record)
        event_date = date.today() + timedelta(days=5 + index)
        row.update(
            _id=ObjectId(),
            title=("Ilmastomarssi", "Mielenosoitus luonnon puolesta",
                   "Yhdessä oikeudenmukaisen tulevaisuuden puolesta")[index % 3],
            slug=f"react-list-{index}", running_number=7000 + index,
            date=event_date.isoformat(), formatted_date=event_date.strftime("%d.%m.%Y"),
            city="Helsinki", address="Kansalaistori", tags=["react-list-test"],
            approved=True, hide=False, rejected=False,
        )
        if scenario in {"missing-times", "continuous-grid"}:
            for field in IMAGE_FIELDS:
                row.pop(field, None)
            event_date = date.today() + timedelta(days=5 + index // 12)
            row.update(date=event_date.isoformat(), formatted_date=event_date.strftime("%d.%m.%Y"),
                       start_time="12:00", end_time="14:00")
            if scenario == "missing-times" and index % 4 == 0:
                row["end_time"] = None
            elif scenario == "missing-times" and index % 4 == 1:
                row["start_time"] = None
            elif scenario == "missing-times" and index % 4 == 2:
                row.pop("start_time", None)
                row.pop("end_time", None)
            if scenario == "continuous-grid" or index % 12 == 0:
                row["cover_picture"] = PHOTO
        if scenario == "organization":
            for field in IMAGE_FIELDS:
                row.pop(field, None)
            event_date = date.today() + timedelta(days=120 if index == 71 else 5 + index // 12)
            row.update(date=event_date.isoformat(), formatted_date=event_date.strftime("%d.%m.%Y"),
                       start_time=None if index % 4 == 0 else "12:00",
                       end_time=None if index % 4 == 1 else "14:00",
                       cancelled=index % 17 == 4, cover_picture=PHOTO,
                       organizers=[{"organization_id": seed["org_id"], "name": "Yhdenvertaisuusverkosto"}])
        if scenario == "pride":
            for field in IMAGE_FIELDS:
                row.pop(field, None)
            cities = (("Helsinki", "Kansalaistori", "60.1699", "24.9384"),
                      ("Turku", "Kauppatori", "60.4518", "22.2666"),
                      ("Tampere", "Keskustori", "61.4978", "23.7610"))
            city, address, latitude, longitude = cities[index % 3]
            row.update(tags=["pride"], city=city, address=address, cover_picture=PHOTO,
                       cancelled=False, latitude=latitude, longitude=longitude,
                       start_time=None if index % 4 == 0 else "12:00",
                       end_time=None if index % 4 == 1 else "14:00")
            if index % 8 == 0:
                row["latitude"] = None
            elif index % 8 == 1:
                row["longitude"] = "invalid"
        db.demonstrations.insert_one(row)
    if scenario == "pride":
        public = db.demonstrations.find_one({"slug": "react-list-0"})
        for label, changes in (("foreign", {"tags": ["other-topic"]}), ("hidden", {"hide": True}),
                               ("unapproved", {"approved": False}), ("rejected", {"rejected": True}),
                               ("past", {"date": (date.today() - timedelta(days=1)).isoformat()})):
            control = deepcopy(public)
            control.update(_id=ObjectId(), slug=f"pride-control-{label}", title=f"Control {label}", **changes)
            db.demonstrations.insert_one(control)
    if scenario == "organization":
        db.organizations.update_one({"_id": seed["org_id"]}, {"$set": {
            "name": "Yhdenvertaisuusverkosto", "logo": PHOTO,
            "description": "Yhteistä toimintaa ja paikallista vaikuttamista eri puolilla Suomea.",
        }})
        public = db.demonstrations.find_one({"slug": "react-list-0"})
        for label, changes in (("foreign", {"organizers": [{"organization_id": db.organizations.find_one({"_id": {"$ne": seed["org_id"]}})["_id"]}]}),
                               ("hidden", {"hide": True}), ("unapproved", {"approved": False}),
                               ("rejected", {"rejected": True})):
            control = deepcopy(public)
            control.update(_id=ObjectId(), slug=f"organization-control-{label}", title=f"Control {label}", **changes)
            db.demonstrations.insert_one(control)
    if scenario == "standard":
        db.demonstrations.update_many({}, {"$unset": {name: "" for name in IMAGE_FIELDS}})

    def assets(route):
        if urlparse(route.request.url).hostname in ALLOWED_HOSTS:
            route.continue_()
        else:
            route.abort()

    def context(width, theme, *, js=True, user=None, locale="fi-FI", role=None):
        ctx = browser.new_context(viewport={"width": width, "height": 1000},
                                  locale=locale, color_scheme=theme, java_script_enabled=js)
        ctx.route("**/*", assets)
        if js:
            ctx.add_init_script(f"localStorage.setItem('theme', {json.dumps(theme)})")
            if scenario in {"missing-times", "continuous-grid", "organization", "pride"}:
                ctx.add_init_script("Object.defineProperty(navigator,'connection',{value:{saveData:true}})")
        if user:
            ctx.add_cookies([{"name": "session", "value": user.get_cookie("session").value, "url": base}])
        page = ctx.new_page()
        page._moso_capture_js = js
        page._moso_capture_theme = theme
        page._moso_capture_role = role or ("authenticated" if user else "anonymous")
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("requestfailed", lambda req: failed.append(req.url))
        return ctx, page

    def shot(page, name, target=None):
        if target:
            page.locator(target).first.evaluate("e => e.scrollIntoView({block:'start',behavior:'instant'})")
            page.evaluate("(window.publicListWindow?.scrollHost || window).scrollBy({top:-80,behavior:'instant'})")
        page.evaluate("document.fonts.ready")
        if scenario in {"organization", "pride"} and page._moso_capture_js:
            page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
            page.evaluate("() => Promise.all(document.getAnimations().filter(a => a.effect?.getTiming().iterations !== Infinity).map(a => a.finished.catch(() => {})))")
        filename = f"{stage}-{name}.png"
        path = output / filename
        page.screenshot(path=str(path), animations="disabled")
        images.append(filename)
        image_hashes[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
        image_states[filename] = {
            "viewport": page.viewport_size, "locale": page.locator("html").get_attribute("lang"),
            "theme": ("dark" if "dark" in (page.locator("html").get_attribute("class") or "") else "light" if "light" in (page.locator("html").get_attribute("class") or "") else page._moso_capture_theme),
            "state": name, "role": page._moso_capture_role,
        }
        if not (scenario == "pride" and stage == "before"):
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), filename

    def save_metadata():
        after = source_inputs()
        if inputs_before != after:
            raise AssertionError("Source changed during visual capture. Rerun with a stable checkout.")
        metadata = {
            "run_id": os.environ.get("MOSO_LIST_CAPTURE_RUN"), "stage": stage,
            "scenario": scenario,
            "images": images, "image_hashes": image_hashes, "image_states": image_states,
            "errors": errors, "failed": sorted(set(failed)), "source_inputs": after,
            "runtime": {"python": platform.python_version()},
            "notes": [
                "Real Flask pages and isolated test Mongo data; actual styles/fonts/assets.",
                "External analytics are blocked; loading/error/attendance responses and module failure are deliberate test states.",
                "Photo states use the repository's existing og-banner.png on a synthetic event, not a production event.",
                *(["Pride primary maps require actual OpenStreetMap tiles; no substitute tiles are supplied.",
                   "Pride map outage, empty/no-coordinate responses, tile warning, list outage, failed module and failed local Leaflet script states are deliberately intercepted.",
                   "Pride map fixtures contain 72 public future events, 54 valid map locations across three cities, nullable clocks and excluded visibility/tag/date controls."] if scenario == "pride" else []),
            ],
        }
        (output / f"{stage}-metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    if scenario == "pride":
        path = "/pride-nakyvaksi"
        fixture = client.get("/api/demonstrations", query_string={"tag": "pride", "per_page": 100}).json
        assert fixture["total"] == 72 and len(fixture["results"]) == 72
        assert all(not row["title"].startswith("Control ") for row in fixture["results"])
        (output / f"{stage}-fixture-response.json").write_text(json.dumps(fixture, indent=2))

        def wait_for_tiles(page):
            page.wait_for_function("() => {const tiles=[...document.querySelectorAll('#pride-map img.leaflet-tile')];return tiles.length>0 && tiles.every(tile=>tile.complete && tile.naturalWidth>0);}", timeout=30000)

        def wait_for_map(page):
            page.locator('#pride-map.leaflet-container').wait_for(state='visible')
            page.wait_for_function("document.querySelectorAll('#pride-map .leaflet-overlay-pane path.leaflet-interactive').length === 54")
            wait_for_tiles(page)
            if stage == 'final':
                summary = page.locator('.pride-map-summary')
                assert summary.get_attribute('data-event-count') == '72'
                assert summary.get_attribute('data-city-count') == '3'
                assert summary.get_attribute('data-mapped-count') == '54'

        def wait_for_list(page, count=12):
            page.wait_for_function("count => document.querySelectorAll('.demo-card').length === count && document.querySelector('#demos-grid')?.getAttribute('aria-busy') === 'false'", arg=count)

        def capture_states():
            for width, theme in ((1440, 'light'), (390, 'dark')):
                ctx, page = context(width, theme)
                mode = {'map': 'hold', 'list': 'normal'}
                pending = []

                def requests(route):
                    query = parse_qs(urlparse(route.request.url).query)
                    if query.get('scope') == ['pride_map']:
                        assert query.get('tag') == ['pride']
                        if mode['map'] == 'hold':
                            pending.append(route)
                            return
                        if mode['map'] == 'empty':
                            payload = {**fixture, 'page': 1, 'total_pages': 1, 'total': 0, 'result_start': 0, 'result_end': 0, 'results': []}
                            route.fulfill(content_type='application/json', body=json.dumps(payload))
                            return
                        if mode['map'] == 'no-coordinates':
                            payload = deepcopy(fixture)
                            for row in payload['results']:
                                row['latitude'] = row['longitude'] = None
                            route.fulfill(content_type='application/json', body=json.dumps(payload))
                            return
                    elif mode['list'] == 'error-once':
                        mode['list'] = 'normal'
                        route.fulfill(status=503, content_type='application/json', body='{"error":"Synthetic listing outage"}')
                        return
                    route.continue_()

                page.route('**/api/demonstrations?*', requests)
                try:
                    page.goto(base + path, wait_until='domcontentloaded')
                    wait_for_list(page)
                    page.wait_for_function("document.querySelector('#pride-map')?.classList.contains('leaflet-container')")
                    assert pending, 'The map request must expose its fixed scope marker.'
                    wait_for_tiles(page)
                    shot(page, f'pride-map-loading-{width}-{theme}', '#pride-map-section')
                    pending.pop(0).fulfill(status=503, content_type='application/json', body='{"error":"Synthetic map outage"}')
                    page.locator('#pride-map-error').wait_for(state='visible')
                    shot(page, f'pride-map-error-{width}-{theme}', '#pride-map-section')
                    mode['map'] = 'normal'
                    page.locator('#pride-map-retry').click()
                    wait_for_map(page)
                    page.locator('#pride-map .leaflet-overlay-pane path.leaflet-interactive').last.click()
                    page.locator('.leaflet-popup-content').wait_for(state='visible')
                    shot(page, f'pride-map-popup-after-retry-{width}-{theme}', '#pride-map-section')
                    page.locator('.leaflet-popup-close-button').click()
                    marker = page.locator('#pride-map .leaflet-overlay-pane path.leaflet-interactive').last
                    assert marker.get_attribute('role') == 'button'
                    assert marker.get_attribute('tabindex') == '0'
                    assert (marker.get_attribute('aria-label') or '').strip()
                    page.keyboard.press('Tab')
                    marker.focus()
                    assert marker.evaluate("element => element === document.activeElement && element.matches(':focus-visible')")
                    shot(page, f'pride-map-marker-keyboard-focus-{width}-{theme}', '#pride-map-section')
                    marker.press('Enter')
                    page.locator('.leaflet-popup-content').wait_for(state='visible')
                    page.wait_for_function("document.activeElement?.matches('#pride-map .leaflet-popup-content a')")
                    shot(page, f'pride-map-marker-keyboard-popup-{width}-{theme}', '#pride-map-section')
                    page.keyboard.press('Escape')
                    page.locator('.leaflet-popup-content').wait_for(state='hidden')
                    assert marker.evaluate('element => element === document.activeElement')

                    mode['map'] = 'empty'
                    page.goto(base + path, wait_until='networkidle')
                    page.locator('#pride-map-empty').wait_for(state='visible')
                    assert page.locator('.pride-map-summary').get_attribute('data-event-count') == '0'
                    wait_for_list(page)
                    shot(page, f'pride-map-empty-{width}-{theme}', '#pride-map-section')
                    mode['map'] = 'no-coordinates'
                    page.goto(base + path, wait_until='networkidle')
                    page.locator('#pride-map-empty').wait_for(state='visible')
                    summary = page.locator('.pride-map-summary')
                    assert summary.get_attribute('data-event-count') == '72'
                    assert summary.get_attribute('data-mapped-count') == '0'
                    wait_for_list(page)
                    shot(page, f'pride-map-no-coordinates-{width}-{theme}', '#pride-map-section')

                    mode['map'] = 'normal'
                    page.route('**://*.tile.openstreetmap.org/**', lambda route: route.abort())
                    page.goto(base + path, wait_until='networkidle')
                    page.locator('.pride-map-tile-warning').wait_for(state='visible')
                    wait_for_list(page)
                    shot(page, f'pride-map-tile-warning-{width}-{theme}', '#pride-map-section')
                    page.unroute('**://*.tile.openstreetmap.org/**')
                    page.goto(base + path, wait_until='networkidle')
                    wait_for_map(page)
                    wait_for_list(page)
                    page.locator('#load-more-btn').click()
                    wait_for_list(page, 24)
                    shot(page, f'pride-loaded-24-{width}-{theme}', "[data-list-page='2'] .demo-card")
                    page.locator('#demo-search').fill('Ilmastomarssi')
                    page.locator('#search-form button[type=submit]').click()
                    wait_for_list(page)
                    assert all('Ilmastomarssi' in value for value in page.locator('.demo-card-title').all_text_contents())
                    shot(page, f'pride-filtered-{width}-{theme}', '.public-list-results')
                    page.locator('#demo-search').fill('no-such-pride-event')
                    page.locator('#search-form button[type=submit]').click()
                    page.locator('#no-results').wait_for(state='visible')
                    shot(page, f'pride-list-empty-{width}-{theme}', '#no-results')
                    assert page.locator('.pride-map-summary').get_attribute('data-event-count') == '72'
                    mode['list'] = 'error-once'
                    page.goto(base + path, wait_until='networkidle')
                    page.locator('#listing-load-error').wait_for(state='visible')
                    shot(page, f'pride-list-error-{width}-{theme}', '#listing-load-error')
                    page.locator('#listing-load-error button').click()
                    wait_for_list(page)
                    shot(page, f'pride-list-retry-{width}-{theme}', '#demos-grid')
                finally:
                    for route in pending:
                        try:
                            route.abort()
                        except Exception:
                            pass
                    ctx.close()

        try:
            for width in (390, 1440):
                for theme in ("light", "dark"):
                    ctx, page = context(width, theme)
                    try:
                        page.goto(base + path, wait_until='networkidle')
                        page.locator('.demo-card').first.wait_for(state='visible')
                        wait_for_map(page)
                        shot(page, f"pride-intro-{width}-{theme}")
                        shot(page, f"pride-map-{width}-{theme}", '#pride-map-section')
                        shot(page, f"pride-events-{width}-{theme}", '#demos')
                        if stage == 'final' and (width, theme) in ((1440, 'light'), (390, 'dark')):
                            shot(page, f'pride-information-{width}-{theme}', '.pride-information')
                            shot(page, f'pride-guidelines-{width}-{theme}', '#demo-guidelines')
                            page.locator('.pride-actions a').first.focus()
                            shot(page, f'pride-keyboard-focus-{width}-{theme}', '.pride-intro')
                    finally:
                        ctx.close()
            if stage == 'final':
                capture_states()
                for width, theme in ((1440, 'light'), (390, 'dark')):
                    ctx, page = context(width, theme, js=False)
                    try:
                        page.goto(base + path, wait_until='networkidle')
                        shot(page, f'pride-no-javascript-{width}-{theme}', '#pride-map-section')
                    finally:
                        ctx.close()
                    ctx, page = context(width, theme)
                    page.route('**/frontend/assets/pride-*.js', lambda route: route.abort())
                    try:
                        page.goto(base + path, wait_until='networkidle')
                        wait_for_list(page)
                        assert page.locator('#pride-map.leaflet-container').count() == 0
                        page.locator('.pride-map-fallback').wait_for(state='visible')
                        shot(page, f'pride-map-module-failure-{width}-{theme}', '#pride-map-section')
                    finally:
                        ctx.close()
                    ctx, page = context(width, theme)
                    blocked_leaflet = []

                    def leaflet_failure(route):
                        if not blocked_leaflet:
                            blocked_leaflet.append(route.request.url)
                            route.abort()
                        else:
                            route.continue_()

                    page.route('**/leaflet/leaflet.js*', leaflet_failure)
                    try:
                        page.goto(base + path, wait_until='networkidle')
                        page.locator('#pride-map-error').wait_for(state='visible')
                        wait_for_list(page)
                        assert blocked_leaflet, 'The local Leaflet script must be blocked once.'
                        shot(page, f'pride-map-library-failure-{width}-{theme}', '#pride-map-section')
                        with page.expect_navigation(wait_until='networkidle'):
                            page.locator('#pride-map-retry').click()
                        wait_for_map(page)
                        wait_for_list(page)
                        assert not page.locator('#pride-map-error').is_visible()
                        shot(page, f'pride-map-library-retry-{width}-{theme}', '#pride-map-section')
                    finally:
                        ctx.close()
                original_locales = app.config.get('BABEL_PUBLIC_LOCALES')
                app.config['BABEL_PUBLIC_LOCALES'] = ['fi', 'en', 'sv']
                try:
                    for width, theme, locale in ((1440, 'light', 'en'), (390, 'dark', 'sv')):
                        ctx, page = context(width, theme, locale=locale)
                        try:
                            ctx.request.get(base + '/set_language/' + locale)
                            page.goto(base + path, wait_until='networkidle')
                            wait_for_map(page)
                            assert page.locator('html').get_attribute('lang') == locale
                            shot(page, f'pride-map-{locale}-{width}-{theme}', '#pride-map-section')
                        finally:
                            ctx.close()
                finally:
                    app.config['BABEL_PUBLIC_LOCALES'] = original_locales
                for width, theme in ((1440, 'light'), (390, 'dark')):
                    ctx, page = context(width, theme)
                    try:
                        page.goto(base + '/demonstrations', wait_until='networkidle')
                        wait_for_list(page)
                        shot(page, f'pride-shared-main-{width}-{theme}')
                    finally:
                        ctx.close()
            assert not errors
            save_metadata()
        except Exception:
            save_metadata()
            raise
        return

    if scenario == "organization":
        path = f"/organization/{seed['org_id']}"
        fixture = client.get("/api/demonstrations", query_string={"organization_id": str(seed["org_id"]), "per_page": 100}).json
        assert fixture["total"] == 72 and len(fixture["results"]) == 72
        assert any(row.get("cancelled") for row in fixture["results"])
        assert any(row["date"] > (date.today() + timedelta(days=60)).isoformat() for row in fixture["results"])
        assert all(not row["title"].startswith("Control ") for row in fixture["results"])
        (output / f"{stage}-fixture-response.json").write_text(json.dumps(fixture, indent=2))

        def settled_org(page, first=1, last=1):
            if stage == "before":
                page.locator(".demo-card").first.wait_for(state="attached")
                return
            page.wait_for_function("([first,last]) => window.publicListWindow?.first === first && window.publicListWindow?.last === last && document.querySelector('#demos-grid')?.getAttribute('aria-busy') === 'false' && !document.querySelector('#load-more-btn').disabled", arg=[first, last])
            assert page.locator(".demo-card").count() == (last - first + 1) * 12

        for width in (390, 1440):
            for theme in ("light", "dark"):
                ctx, page = context(width, theme)
                try:
                    page.goto(base + path + "?per_page=12", wait_until="networkidle")
                    settled_org(page)
                    shot(page, f"organization-profile-{width}-{theme}")
                    if stage == "final":
                        assert page.locator('.public-search-submit').evaluate("e => getComputedStyle(e).backgroundColor") == 'rgb(255, 102, 0)'
                    shot(page, f"organization-events-{width}-{theme}", "#demos")
                finally:
                    ctx.close()
        if stage == "before":
            save_metadata()
            return

        for width, theme in ((390, "dark"), (1440, "light")):
            ctx, page = context(width, theme)
            try:
                page.goto(base + "/demonstrations?per_page=12", wait_until="networkidle")
                page.locator(".demo-card").first.wait_for(state="visible")
                shot(page, f"shared-main-{width}-{theme}")
                page.goto(base + path + "?per_page=12", wait_until="networkidle")
                settled_org(page)
                page.locator("#load-more-btn").click()
                settled_org(page, 1, 2)
                shot(page, f"organization-loaded-24-{width}-{theme}", "[data-list-page='2'] .demo-card")
                page.locator("#demo-search").fill("Ilmastomarssi")
                page.locator("#search-form button[type=submit]").click()
                settled_org(page)
                assert all("Ilmastomarssi" in text for text in page.locator(".demo-card-title").all_text_contents())
                shot(page, f"organization-filtered-{width}-{theme}", ".public-list-tools")
                page.locator("#demo-search").fill("no-such-organization-event")
                page.locator("#search-form button[type=submit]").click()
                page.locator("#no-results").wait_for(state="visible")
                shot(page, f"organization-empty-{width}-{theme}", "#no-results")
                page.locator("#clear-filters-btn").click()
                settled_org(page)
                page.goto(base + path + "?per_page=12&page=5", wait_until="networkidle")
                settled_org(page, 5, 5)
                page.locator("#load-previous-btn").click()
                settled_org(page, 4, 5)
                shot(page, f"organization-restored-{width}-{theme}", ".public-list-results")
            finally:
                ctx.close()
            ctx, page = context(width, theme)
            pending = []
            page.route("**/api/demonstrations?*", lambda route: pending.append(route))
            try:
                page.goto(base + path, wait_until="domcontentloaded")
                page.locator(".loading-container").wait_for(state="visible")
                shot(page, f"organization-loading-{width}-{theme}", ".public-list-results")
                pending.pop().fulfill(status=503, content_type="application/json", body="{}")
                page.locator("#listing-load-error").wait_for(state="visible")
                shot(page, f"organization-initial-error-{width}-{theme}", "#listing-load-error")
                page.unroute("**/api/demonstrations?*")
                page.locator("#listing-load-error button").click()
                settled_org(page)
                shot(page, f"organization-initial-retry-{width}-{theme}", "#demos-grid")
                page.route("**/api/demonstrations?*", lambda route: route.fulfill(status=503, content_type="application/json", body="{}"))
                page.locator("#load-more-btn").click()
                page.locator("#listing-load-error").wait_for(state="visible")
                assert page.locator(".demo-card").count() == 12
                shot(page, f"organization-append-error-{width}-{theme}", "#listing-load-error")
                page.unroute("**/api/demonstrations?*")
                page.locator("#listing-load-error button").click()
                settled_org(page, 1, 2)
                shot(page, f"organization-append-retry-{width}-{theme}", "[data-list-page='2']")
            finally:
                ctx.close()
        for fixture_name, label in (("user_client", "organization-admin"), ("admin_client", "global-admin")):
            user = request.getfixturevalue(fixture_name)
            ctx, page = context(1440, "light", user=user, role=label)
            try:
                page.goto(base + path, wait_until="networkidle")
                settled_org(page)
                assert page.locator("#org-follow-btn").is_visible()
                assert page.locator("#toolbox-sidebar").count() == 1
                shot(page, f"organization-{label}-profile-1440-light")
                shot(page, f"organization-{label}-events-1440-light", "#demos")
            finally:
                ctx.close()
        invited = request.getfixturevalue("friend_client")
        db.organizations.update_one({"_id": seed["org_id"]}, {"$push": {"invitations": {"email": "bob@example.test", "role": "member"}}})
        for width in (390, 1440):
            for theme in ("light", "dark"):
                ctx, page = context(width, theme, user=invited, role="invited-user")
                try:
                    page.goto(base + path, wait_until="networkidle")
                    settled_org(page)
                    page.locator('.invite-banner').wait_for(state='visible')
                    shot(page, f"organization-invitation-{width}-{theme}", ".invite-banner")
                finally:
                    ctx.close()
        original_locales = app.config.get('BABEL_PUBLIC_LOCALES')
        app.config['BABEL_PUBLIC_LOCALES'] = ['fi', 'en', 'sv']
        try:
            for width, theme, locale in ((1440, "light", "en"), (390, "dark", "sv")):
                ctx, page = context(width, theme, locale=locale)
                try:
                    page.route('**/api/demonstrations?*', lambda route: route.fulfill(content_type='application/json', body=json.dumps({"page": 1, "per_page": 12, "total_pages": 1, "total": 0, "results": []})))
                    ctx.request.get(base + '/set_language/' + locale)
                    page.goto(base + path, wait_until='networkidle')
                    page.locator('#no-results').wait_for(state='visible')
                    assert page.locator('html').get_attribute('lang') == locale
                    shot(page, f"organization-empty-{locale}-{width}-{theme}", '#no-results')
                finally:
                    ctx.close()
        finally:
            app.config['BABEL_PUBLIC_LOCALES'] = original_locales
        assert not errors
        save_metadata()
        return

    if scenario == "continuous-grid":
        def settled_grid(page, first, last):
            page.wait_for_function("([first,last]) => window.publicListWindow?.first === first && window.publicListWindow?.last === last && document.querySelector('#demos-grid')?.getAttribute('aria-busy') === 'false' && !document.querySelector('#load-more-btn').disabled", arg=[first, last])
            assert page.locator(".demo-card").count() == (last - first + 1) * 12

        matrix = [("/demonstrations", "all", 1680, theme) for theme in ("light", "dark")] if stage == "before" else [
            (path, name, width, theme)
            for path, name in (("/demonstrations", "all"), ("/city/Helsinki", "city"), ("/tag/react-list-test", "tag"))
            for width in (390, 1440, 1680) for theme in ("light", "dark")
        ]
        for path, name, width, theme in matrix:
            ctx, page = context(width, theme)
            try:
                page.goto(base + path + "?per_page=12", wait_until="networkidle")
                settled_grid(page, 1, 1)
                page.locator("#load-more-btn").click()
                settled_grid(page, 1, 2)
                page.evaluate("document.fonts.ready")
                if width == 1680:
                    boundary = page.locator(".demo-card").evaluate_all("cards => [cards[11].getBoundingClientRect().top, cards[12].getBoundingClientRect().top]")
                    if stage == "final":
                        assert abs(boundary[0] - boundary[1]) <= 1, boundary
                    else:
                        assert boundary[1] > boundary[0] + 100, boundary
                shot(page, f"grid-boundary-{name}-{width}-{theme}", "[data-list-page='1'] .demo-card:last-child")
            finally:
                ctx.close()
        if stage == "final":
            for theme in ("light", "dark"):
                ctx, page = context(1680, theme)
                try:
                    page.goto(base + "/demonstrations?per_page=12", wait_until="networkidle")
                    settled_grid(page, 1, 1)
                    for last in range(2, 6):
                        page.locator("#load-more-btn").click()
                        settled_grid(page, 1, last)
                    anchor = page.locator("[data-list-page='5'] .demo-card").first
                    anchor.scroll_into_view_if_needed()
                    page.mouse.move(0, 0)
                    anchor.evaluate("e => Promise.all(e.getAnimations().map(a => a.finished.catch(() => {})))")
                    before = anchor.bounding_box()
                    page.locator("#load-more-btn").dispatch_event("click")
                    settled_grid(page, 2, 6)
                    after = anchor.bounding_box()
                    assert all(abs(after[axis] - before[axis]) <= 1 for axis in ("x", "y")), (before, after)
                    shot(page, f"grid-evicted-1680-{theme}", "[data-list-page='5'] .demo-card")
                    page.set_viewport_size({"width": 390, "height": 1000})
                    page.wait_for_function("getComputedStyle(document.querySelector('.demo-card')).gridColumnStart === '1'")
                    shot(page, f"grid-resized-390-{theme}", "[data-list-page='5'] .demo-card")
                finally:
                    ctx.close()
            for width, theme in ((390, "dark"), (1680, "light")):
                ctx, page = context(width, theme)
                try:
                    page.goto(base + "/demonstrations?page=6&per_page=12", wait_until="networkidle")
                    settled_grid(page, 6, 6)
                    page.locator("#load-previous-btn").click()
                    settled_grid(page, 5, 6)
                    shot(page, f"grid-restored-previous-{width}-{theme}", "[data-list-page='5'] .demo-card:last-child")
                finally:
                    ctx.close()
            user = request.getfixturevalue("user_client")
            ctx, page = context(1680, "light", user=user)
            try:
                page.goto(base + "/demonstrations?per_page=12", wait_until="networkidle")
                settled_grid(page, 1, 1)
                page.locator("#load-more-btn").click()
                settled_grid(page, 1, 2)
                shot(page, "grid-authenticated-1680-light", "[data-list-page='1'] .demo-card:last-child")
                page.locator("[data-list-page='2'] .demo-card").first.focus()
                shot(page, "grid-keyboard-focus-1680-light", "[data-list-page='2'] .demo-card")
            finally:
                ctx.close()
            for width, theme in ((390, "dark"), (1440, "light")):
                ctx, page = context(width, theme)
                try:
                    page.goto(base + "/demonstrations?search=no-such-event", wait_until="networkidle")
                    page.locator("#no-results").wait_for(state="visible")
                    assert not page.locator("#demos-grid").is_visible()
                    shot(page, f"grid-empty-{width}-{theme}", "#no-results")
                    pending = []
                    page.route("**/api/demonstrations?*", lambda route: pending.append(route))
                    page.locator("#demo-search").fill("loading")
                    page.locator("#search-form button[type='submit']").click()
                    page.locator(".loading-container").wait_for(state="visible")
                    shot(page, f"grid-loading-{width}-{theme}", ".loading-container")
                finally:
                    ctx.close()
        assert not errors
        save_metadata()
        return

    if scenario == "missing-times":
        payload = client.get("/api/demonstrations?tag=react-list-test&page=6&per_page=12").json
        assert payload["total"] == 72 and len(payload["results"]) == 12
        assert any(row.get("end_time") is None for row in payload["results"])
        assert any(row.get("start_time") is None for row in payload["results"])
        (output / f"{stage}-fixture-response.json").write_text(json.dumps(payload, indent=2))

        def settled(page, first, last):
            page.wait_for_function("([first,last]) => window.publicListWindow?.first === first && window.publicListWindow?.last === last && document.querySelector('#demos-grid')?.getAttribute('aria-busy') === 'false'", arg=[first, last])
            if stage == "final":
                assert page.locator(".demo-card").count() == (last - first + 1) * 12
                page.locator(".demo-card").first.wait_for(state="visible")
                assert not page.locator("#listing-load-error").is_visible()
            else:
                assert page.locator(".demo-card").count() == 0

        for path, name in (("/demonstrations", "all"), ("/city/Helsinki", "city"), ("/tag/react-list-test", "tag")):
            for width in (390, 1440):
                for theme in ("light", "dark"):
                    ctx, page = context(width, theme)
                    try:
                        page.goto(base + path + "?page=6&per_page=12", wait_until="networkidle")
                        settled(page, 6, 6)
                        if stage == "final":
                            picture = page.locator(".demo-card-image img").first
                            picture.scroll_into_view_if_needed()
                            page.wait_for_function("() => Array.from(document.querySelectorAll('.demo-card-image img')).some(image => image.complete && image.naturalWidth > 0)")
                        shot(page, f"missing-times-{name}-{width}-{theme}", ".public-list-results")
                        if name == "all":
                            page.locator("#load-previous-btn").click()
                            settled(page, 5, 6)
                            shot(page, f"missing-times-previous-{width}-{theme}", ".public-list-results")
                            page.goto(base + path + "?page=1&per_page=12", wait_until="networkidle")
                            settled(page, 1, 1)
                            page.locator("#load-more-btn").click()
                            settled(page, 1, 2)
                    finally:
                        ctx.close()
        if stage == "final":
            for width, theme in ((390, "light"), (1440, "dark")):
                ctx, page = context(width, theme)
                bad_pages = {1, 2}

                def inject_render_fault(route):
                    response = route.fetch()
                    payload = response.json()
                    if payload["page"] in bad_pages:
                        bad_pages.remove(payload["page"])
                        payload["results"][0]["title"] = {}
                    route.fulfill(response=response, json=payload)

                page.route("**/api/demonstrations?*", inject_render_fault)
                try:
                    page.goto(base + "/demonstrations?per_page=12", wait_until="networkidle")
                    page.locator("#listing-load-error").wait_for(state="visible")
                    assert page.locator(".demo-card").count() == 0
                    assert not page.locator("#listing-result-summary").is_visible()
                    shot(page, f"render-initial-error-{width}-{theme}", ".public-list-results")
                    page.locator("#listing-load-error button").click()
                    settled(page, 1, 1)
                    shot(page, f"render-initial-retry-{width}-{theme}", "#demos-grid")
                    summary = page.locator("#listing-result-summary").inner_text()
                    previous_url = page.url
                    page.locator("#load-more-btn").click()
                    page.locator("#listing-load-error").wait_for(state="visible")
                    assert page.locator(".demo-card").count() == 12
                    assert page.locator("#listing-result-summary").inner_text() == summary
                    assert page.url == previous_url
                    shot(page, f"render-append-error-{width}-{theme}", "#listing-load-error")
                    page.locator("#listing-load-error button").click()
                    settled(page, 1, 2)
                    shot(page, f"render-append-retry-{width}-{theme}", "[data-list-page='2']")
                finally:
                    ctx.close()
        if stage == "before":
            assert errors and all("null" in error and "split" in error for error in errors)
        else:
            assert not errors
        save_metadata()
        return

    for path, name in (("/demonstrations", "all"), ("/city/Helsinki", "city"), ("/tag/react-list-test", "tag")):
        for width in (390, 1440):
            for theme in ("light", "dark"):
                ctx, page = context(width, theme)
                try:
                    page.goto(base + path, wait_until="networkidle")
                    page.locator(".demo-card").first.wait_for(state="visible")
                    shot(page, f"{name}-{width}-{theme}")
                    shot(page, f"{name}-cards-{width}-{theme}", "#demos-grid")
                finally:
                    ctx.close()
    if stage == "before":
        save_metadata()
        return

    for width, theme in ((390, "light"), (1440, "dark")):
        suffix = f"{width}-{theme}"
        ctx, page = context(width, theme)
        try:
            page.goto(base + "/tag/react-list-test?search=no-such-event", wait_until="networkidle")
            page.locator("#no-results").wait_for(state="visible")
            shot(page, "empty-" + suffix, "#no-results")
            page.locator("#clear-filters-btn").click()
            page.locator(".demo-card").first.wait_for(state="visible")
            page.goto(base + "/demonstrations", wait_until="networkidle")
            page.locator("#city_input").fill("Hel")
            page.locator("#city_input").press("ArrowDown")
            shot(page, "city-suggestions-" + suffix, "#search-form")
            page.locator("#city_input").press("Escape")
            page.locator("#date_start").scroll_into_view_if_needed()
            page.locator("#date_start").focus()
            page.keyboard.press("ArrowDown")
            page.locator("#date_start-calendar").wait_for(state="visible")
            shot(page, "calendar-" + suffix)
            page.keyboard.press("Escape")
            pending = []
            page.route("**/api/demonstrations?*", lambda route: pending.append(route))
            page.goto(base + "/demonstrations", wait_until="domcontentloaded")
            page.locator('#demos-grid [role="status"]').wait_for(state="visible")
            shot(page, "loading-" + suffix, "#demos-grid")
            pending.pop().fulfill(status=503, content_type="application/json", body="{}")
            page.locator("#listing-load-error").wait_for(state="visible")
            shot(page, "error-" + suffix, "#listing-load-error")
        finally:
            ctx.close()
        user = request.getfixturevalue("user_client")
        ctx, page = context(width, theme, user=user)
        try:
            attendance = []
            page.route("**/api/friends-attending", lambda route: attendance.append(route))
            page.goto(base + "/demonstrations", wait_until="domcontentloaded")
            page.locator(".demo-card").first.wait_for(state="visible")
            shot(page, "attendance-loading-" + suffix, "#demos-grid")
            for route in attendance:
                data = {key: [] for key in route.request.post_data_json["demo_ids"]}
                first = next(iter(data), None)
                if first:
                    data[first] = [{"name": "Esimerkkikaveri", "avatar": "/static/icons/icon_favicon-32x32.png"}]
                route.fulfill(content_type="application/json", body=json.dumps(data))
            page.locator(".demo-card-friends").first.wait_for(state="visible")
            shot(page, "attendance-" + suffix, "#demos-grid")
        finally:
            ctx.close()

    for locale, width, theme in (("en", 1440, "light"), ("sv", 390, "dark")):
        app.config["BABEL_PUBLIC_LOCALES"] = ["fi", "en", "sv"]
        ctx, page = context(width, theme, locale=locale)
        try:
            page.goto(base + "/set_language/" + locale, wait_until="networkidle")
            page.goto(base + "/demonstrations?city=Helsinki,Tampere", wait_until="networkidle")
            page.locator(".demo-card").first.wait_for(state="visible")
            shot(page, f"localized-{locale}-{width}-{theme}")
        finally:
            ctx.close()
    for js, name in ((False, "nojs"), (True, "failed-module")):
        ctx, page = context(390, "light", js=js)
        try:
            if js:
                page.route("**/frontend/assets/listing-*.js", lambda route: route.abort())
            page.goto(base + "/demonstrations", wait_until="networkidle")
            shot(page, name + "-390-light")
        finally:
            ctx.close()

    # A positive image case follows the real Mongo -> API -> React -> decoded bytes path.
    app.config["BABEL_PUBLIC_LOCALES"] = ["fi"]
    photo_record = db.demonstrations.find_one({"slug": "react-list-0"})
    db.demonstrations.update_one({"_id": photo_record["_id"]}, {"$set": {"cover_picture": PHOTO}})
    for width in (390, 1440):
        for theme in ("light", "dark"):
            ctx, page = context(width, theme)
            try:
                page.goto(base + "/tag/react-list-test", wait_until="networkidle")
                selector = f'[data-demo-id="{photo_record["_id"]}"] .demo-card-image img'
                picture = page.locator(selector)
                picture.scroll_into_view_if_needed()
                page.wait_for_function(
                    "selector => { const image=document.querySelector(selector); return image?.complete && image.naturalWidth > 0; }",
                    arg=selector,
                )
                assert picture.get_attribute("src") == PHOTO
                shot(page, f"photo-{width}-{theme}", f'[data-demo-id="{photo_record["_id"]}"]')
            finally:
                ctx.close()
    save_metadata()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    result = yield
    if result.excinfo is None:
        capture(item)
