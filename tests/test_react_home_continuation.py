"""Home page continuation in the standalone React host.

The picks on the home page flow into the chronological public listing, so a
visitor who wants more events gets them in place instead of reaching the Pride
campaign. These tests run the built host (`npm run app:build`) against a stub
of the public Go API; no MongoDB or Flask is involved.
"""
from __future__ import annotations

from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time
from urllib.parse import parse_qs, urlparse
import urllib.request

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER_BUILD = ROOT / "frontend" / "dist" / "server" / "render.js"
CLIENT_MANIFEST = ROOT / "frontend" / "dist" / "client" / ".vite" / "manifest.json"
PER_PAGE = 12
TOTAL = 40
PICKS = 6

pytestmark = pytest.mark.skipif(
    not SERVER_BUILD.exists() or not CLIENT_MANIFEST.exists() or not shutil.which("node"),
    reason="Run `npm run app:build` with Node available to test the React host.",
)


def _events():
    start = date.today()
    return [{
        "_id": f"{index:024x}", "title": f"Tapahtuma {index + 1}",
        "date": (start + timedelta(days=index // 3)).isoformat(),
        "start_time": "12:00", "end_time": "14:00", "city": "Helsinki",
        "address": f"Esimerkkikatu {index + 1}", "tags": [],
        "detail_url": f"/demonstration/{index:024x}",
    } for index in range(TOTAL)]


class _Api:
    def __init__(self):
        self.events = _events()
        self.requests: list[dict] = []
        self.fail = False
        self.home_ids = [event["_id"] for event in self.events[:PICKS]]

    def handler(self):
        api = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _json(self, body, status=200):
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                url = urlparse(self.path)
                if url.path == "/api/public-status":
                    return self._json({"available": True})
                if url.path == "/session":
                    return self._json({"authenticated": False, "locale": "fi", "locales": [{"code": "fi", "name": "Suomi"}]})
                if url.path == "/api/home":
                    picks = [event for event in api.events if event["_id"] in api.home_ids]
                    return self._json({"events": picks, "recommended": False})
                if url.path == "/api/demonstrations":
                    query = {key: values[0] for key, values in parse_qs(url.query).items()}
                    api.requests.append(query)
                    if api.fail:
                        return self._json({"error": "unavailable"}, 503)
                    page, per = int(query["page"]), int(query["per_page"])
                    rows = api.events[(page - 1) * per: page * per]
                    return self._json({"page": page, "per_page": per, "total": TOTAL,
                                       "total_pages": -(-TOTAL // per), "result_start": 0,
                                       "result_end": 0, "results": rows})
                return self._json({"error": "not found"}, 404)

        return Handler


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def home_host():
    api = _Api()
    server = ThreadingHTTPServer(("127.0.0.1", 0), api.handler())
    threading.Thread(target=server.serve_forever, daemon=True).start()
    api_origin = f"http://127.0.0.1:{server.server_address[1]}"
    port = _free_port()
    env = {**os.environ, "APP_PORT": str(port), "PUBLIC_API_BASE": f"{api_origin}/api",
           "SESSION_URL": f"{api_origin}/session",
           "STATIC_DIR": str(ROOT / "mielenosoitukset_fi" / "static")}
    process = subprocess.Popen(["node", "frontend/server.mjs"], cwd=ROOT, env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                with urllib.request.urlopen(f"{base}/", timeout=1) as response:
                    if response.status == 200:
                        break
            except Exception:
                time.sleep(0.1)
        else:
            pytest.fail("React host did not start")
        yield base, api
    finally:
        process.terminate()
        process.wait(timeout=10)
        server.shutdown()


def _scroll_until(page, condition, steps=40):
    page.mouse.move(10, 400)
    for _ in range(steps):
        if page.evaluate(condition):
            return
        page.mouse.wheel(0, 700)
        page.wait_for_timeout(150)
    raise AssertionError(f"Condition not reached while scrolling: {condition}")


def test_continuation_keeps_a_real_listing_link_and_puts_pride_after_the_events(home_host, browser_page):
    base, _ = home_host
    page = browser_page
    page.goto(f"{base}/")
    page.wait_for_selector(".home-events .demo-card")
    order = page.eval_on_selector_all(".home-page > *", "nodes => nodes.map(node => node.className)")
    assert order == ["home-intro", "home-events", "home-more", "home-campaign"]
    assert page.text_content("#home-more-title") == "Kaikki tulevat mielenosoitukset"
    # Keyboard users, crawlers and anyone who prefers filters keep the real URL.
    assert page.get_attribute(".home-more-next a", "href") == "/demonstrations"
    assert page.get_attribute(".home-more-status", "role") == "status"


def test_scrolling_continues_into_the_listing_without_repeating_picks(home_host, browser_page):
    base, api = home_host
    page = browser_page
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{base}/")
    page.wait_for_selector(".home-events .demo-card")
    assert not api.requests, "Nothing beyond the picks loads before the visitor scrolls"

    _scroll_until(page, "document.querySelectorAll('.home-more-grid .demo-card').length >= 18 && !document.querySelector('.home-more-placeholder')")
    page.wait_for_timeout(600)
    assert [request["page"] for request in api.requests] == ["1", "2"], "Only the automatic pages load by scrolling"
    assert all(request["per_page"] == str(PER_PAGE) and request["lang"] == "fi" for request in api.requests)
    ids = page.eval_on_selector_all(".home-more-grid .demo-card", "cards => cards.map(card => card.dataset.demoId)")
    assert len(ids) == len(set(ids)) == PER_PAGE * 2 - PICKS
    assert not set(ids) & set(api.home_ids)
    assert page.text_content(".home-more-status") == "Lisää mielenosoituksia ladattu: 12."
    # Automatic loading stops, so the footer and the campaign stay reachable.
    _scroll_until(page, "document.querySelector('.home-campaign').getBoundingClientRect().top < innerHeight")
    page.wait_for_timeout(400)
    assert len(api.requests) == 2

    page.focus(".home-more-button")
    page.keyboard.press("Enter")
    page.wait_for_function("document.activeElement.dataset.demoId === '%024x'" % (PER_PAGE * 2))
    assert page.locator(".home-more-grid .demo-card").count() == PER_PAGE * 3 - PICKS
    page.click(".home-more-button")
    page.wait_for_selector(".home-more-end")
    assert page.locator(".home-more-button").count() == 0
    assert page.locator(".home-more-grid .demo-card").count() == TOTAL - PICKS
    assert "Olet selannut kaikki tulevat mielenosoitukset." in page.text_content(".home-more-status")
    assert page.get_attribute(".home-more-next a", "href") == "/demonstrations"


def test_failed_continuation_offers_retry_and_keeps_the_listing_link(home_host, browser_page):
    base, api = home_host
    api.fail = True
    page = browser_page
    page.goto(f"{base}/")
    page.wait_for_selector(".home-events .demo-card")
    _scroll_until(page, "!!document.querySelector('.home-more-error')")
    assert page.text_content(".home-more-status") == "Lisää mielenosoituksia ei voitu ladata. Yritä uudelleen."
    assert page.get_attribute(".home-more-next a", "href") == "/demonstrations"
    api.fail = False
    page.click(".home-more-next button")
    page.wait_for_selector(".home-more-grid .demo-card")
    assert page.locator(".home-more-error").count() == 0


def test_reduced_motion_disables_the_arrival_animation(home_host, browser_page):
    base, _ = home_host
    page = browser_page
    page.emulate_media(reduced_motion="reduce")
    page.goto(f"{base}/")
    page.wait_for_selector(".home-events .demo-card")
    _scroll_until(page, "!!document.querySelector('.home-more-grid .demo-card')")
    assert page.eval_on_selector(".home-more-grid .demo-card", "card => getComputedStyle(card).animationName") == "none"
    assert page.eval_on_selector(".home-more-cue", "cue => getComputedStyle(cue, '::after').animationName") == "none"
