"""Front page shortcuts, the single exit after the picks and the resting Pride banner.

Runs the built React host (`npm run app:build`) against a stub of the public Go
API; no MongoDB or Flask is involved.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time
from urllib.parse import urlparse
import urllib.request

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER_BUILD = ROOT / "frontend" / "dist" / "server" / "render.js"
CLIENT_MANIFEST = ROOT / "frontend" / "dist" / "client" / ".vite" / "manifest.json"

pytestmark = pytest.mark.skipif(
    not SERVER_BUILD.exists() or not CLIENT_MANIFEST.exists() or not shutil.which("node"),
    reason="Run `npm run app:build` with Node available to test the React host.",
)

EVENTS = [{
    "_id": f"{index:024x}", "title": f"Tapahtuma {index + 1}", "date": "2026-11-20",
    "start_time": "12:00", "end_time": "14:00", "city": "Helsinki", "address": f"Esimerkkikatu {index + 1}",
    "tags": [], "detail_url": f"/demonstration/{index:024x}",
} for index in range(6)]


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        path = urlparse(self.path).path
        body = {"available": True} if path == "/api/public-status" else {
            "authenticated": False, "locale": "fi", "locales": [{"code": "fi", "name": "Suomi"}],
        } if path == "/session" else {"events": EVENTS, "recommended": False} if path == "/api/home" else {}
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture
def home_host():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    api = f"http://127.0.0.1:{server.server_address[1]}"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {**os.environ, "APP_PORT": str(port), "PUBLIC_API_BASE": f"{api}/api", "SESSION_URL": f"{api}/session",
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
        yield base
    finally:
        process.terminate()
        process.wait(timeout=10)
        server.shutdown()


def _open(page, base, when):
    # Noon UTC is the same calendar day in Helsinki all year.
    page.clock.set_fixed_time(f"{when}T12:00:00Z")
    page.goto(f"{base}/")
    page.wait_for_selector(".home-events .demo-card")


def test_shortcuts_exit_and_resting_pride_banner_order(home_host, browser_page):
    _open(browser_page, home_host, "2026-11-11")
    order = browser_page.eval_on_selector_all(".home-page > *", "nodes => nodes.map(node => node.className)")
    assert order == ["home-intro", "home-events", "home-all-link"], "Pride rests until 1 January 2027"
    assert browser_page.get_attribute(".home-quick a >> nth=0", "href") == "/mielenosoitukset-tanaan"
    assert browser_page.text_content(".home-quick a >> nth=0") == "Tänään"
    assert browser_page.get_attribute(".home-all-link", "href") == "/demonstrations"
    assert browser_page.text_content(".home-all-link").strip().startswith("Kaikki tulevat mielenosoitukset")
    # The exit is the picks' only way on, so the heading carries no second link.
    assert browser_page.locator(".home-section-heading a").count() == 0


def test_pride_returns_after_the_exit_on_new_year(home_host, browser_page):
    _open(browser_page, home_host, "2027-01-01")
    order = browser_page.eval_on_selector_all(".home-page > *", "nodes => nodes.map(node => node.className)")
    assert order == ["home-intro", "home-events", "home-all-link", "home-campaign"]
    _open(browser_page, home_host, "2026-12-31")
    assert browser_page.locator(".home-campaign").count() == 0


@pytest.mark.parametrize("today, start, end", [
    ("2026-11-11", "2026-11-14", "2026-11-15"),  # Wednesday: the coming Saturday and Sunday
    ("2026-11-13", "2026-11-14", "2026-11-15"),  # Friday
    ("2026-11-14", "2026-11-14", "2026-11-15"),  # Saturday: today and tomorrow
    ("2026-11-15", "2026-11-15", "2026-11-15"),  # Sunday: only today
    ("2026-11-16", "2026-11-21", "2026-11-22"),  # Monday
])
def test_weekend_shortcut_uses_saturday_and_sunday(home_host, browser_page, today, start, end):
    _open(browser_page, home_host, today)
    href = browser_page.get_attribute(".home-quick a >> nth=1", "href")
    assert browser_page.text_content(".home-quick a >> nth=1") == "Viikonloppuna"
    assert href == f"/demonstrations?date_start={start}&date_end={end}"


def test_transition_stylesheet_is_shared_and_respects_reduced_motion(home_host):
    css = (ROOT / "mielenosoitukset_fi" / "static" / "css" / "page-transition.css").read_text()
    assert "@view-transition { navigation: auto; }" in css
    reduced = css[css.index("prefers-reduced-motion"):]
    assert "navigation: none" in reduced
    with urllib.request.urlopen(f"{home_host}/") as response:
        assert "/static/css/page-transition.css" in response.read().decode()
    render = (ROOT / "frontend" / "src" / "app" / "render.tsx").read_text()
    assert render.count("PAGE_TRANSITION_STYLESHEET") == 3, "Defined once, used by home and listing only"
