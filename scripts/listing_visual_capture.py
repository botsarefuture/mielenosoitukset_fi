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
from urllib.parse import urlparse

from bson import ObjectId
import pytest

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_HOSTS = {
    "localhost", "127.0.0.1", "cdn2.mielenosoitukset.fi",
    "fonts.googleapis.com", "fonts.gstatic.com", "cdn.socket.io",
}
IMAGE_FIELDS = ("cover_picture", "cover_image", "preview_image", "img", "image_url")
PHOTO = "/static/kampanja/og-banner.png"


def source_inputs() -> dict:
    """Record the actual checkout and dirty inputs, including untracked files."""
    def git(*args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()

    changed = set(filter(None, git("diff", "--name-only", "-z", "HEAD").split("\0")))
    changed.update(filter(None, git("ls-files", "--others", "--exclude-standard", "-z").split("\0")))
    changed.update({
        "tests/conftest.py", "config.py", "mielenosoitukset_fi/app.py",
        "mielenosoitukset_fi/basic_routes.py", "mielenosoitukset_fi/api/routes.py",
        "scripts/listing_visual_capture.py", "scripts/verify_react_listings.py",
        "mielenosoitukset_fi/templates/base.html",
        "mielenosoitukset_fi/templates/_layouts/demonstration-list.html",
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
    for index in range(15):
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
        db.demonstrations.insert_one(row)
    db.demonstrations.update_many({}, {"$unset": {name: "" for name in IMAGE_FIELDS}})

    def assets(route):
        if urlparse(route.request.url).hostname in ALLOWED_HOSTS:
            route.continue_()
        else:
            route.abort()

    def context(width, theme, *, js=True, user=None, locale="fi-FI"):
        ctx = browser.new_context(viewport={"width": width, "height": 1000},
                                  locale=locale, color_scheme=theme, java_script_enabled=js)
        ctx.route("**/*", assets)
        if js:
            ctx.add_init_script(f"localStorage.setItem('theme', {json.dumps(theme)})")
        if user:
            ctx.add_cookies([{"name": "session", "value": user.get_cookie("session").value, "url": base}])
        page = ctx.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("requestfailed", lambda req: failed.append(req.url))
        return ctx, page

    def shot(page, name, target=None):
        if target:
            page.locator(target).first.evaluate("e => e.scrollIntoView({block:'start',behavior:'instant'})")
            page.evaluate("(window.publicListWindow?.scrollHost || window).scrollBy({top:-80,behavior:'instant'})")
        page.evaluate("document.fonts.ready")
        filename = f"{stage}-{name}.png"
        path = output / filename
        page.screenshot(path=str(path), animations="disabled")
        images.append(filename)
        image_hashes[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
        image_states[filename] = {
            "viewport": page.viewport_size, "locale": page.locator("html").get_attribute("lang"),
            "theme": "dark" if "dark" in (page.locator("html").get_attribute("class") or "") else "light",
            "state": name,
        }
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), filename

    def save_metadata():
        after = source_inputs()
        if inputs_before != after:
            raise AssertionError("Source changed during visual capture. Rerun with a stable checkout.")
        metadata = {
            "run_id": os.environ.get("MOSO_LIST_CAPTURE_RUN"), "stage": stage,
            "images": images, "image_hashes": image_hashes, "image_states": image_states,
            "errors": errors, "failed": sorted(set(failed)), "source_inputs": after,
            "runtime": {"python": platform.python_version()},
            "notes": [
                "Real Flask pages and isolated test Mongo data; actual styles/fonts/assets.",
                "External analytics are blocked; loading/error/attendance responses and module failure are deliberate test states.",
                "Photo states use the repository's existing og-banner.png on a synthetic event, not a production event.",
            ],
        }
        (output / f"{stage}-metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

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
