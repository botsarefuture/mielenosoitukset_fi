import hashlib
import json
import os
import socket
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(os.environ["WT"])
OUT = Path(os.environ["OUT"])
PAGES = ["/info", "/ohjeet", "/privacy", "/terms", "/upcoming/translations/"]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def slug(path):
    return path.strip("/").replace("/", "-") or "home"


def test_capture(app, db, seeded_data, live_server, user_client, playwright_browser):
    OUT.mkdir(parents=True, exist_ok=True)
    port, api_port = free_port(), free_port()
    api = subprocess.Popen([os.environ.get("MOSO_API_BIN", "/tmp/moso-api")], env={**os.environ, "MONGODB_URI": "mongodb://127.0.0.1:27017",
                           "MONGODB_DATABASE": db.name, "API_ADDR": f"127.0.0.1:{api_port}"})
    api_base = f"http://127.0.0.1:{api_port}/api"
    env = {**os.environ, "APP_PORT": str(port), "APP_ADDR": "127.0.0.1", "APP_ORIGIN": f"http://127.0.0.1:{port}",
           "FLASK_API_ORIGIN": live_server, "PUBLIC_API_BASE": api_base, "PUBLIC_API_LOCAL": api_base,
           "STATIC_DIR": str(ROOT / "mielenosoitukset_fi/static")}
    host = subprocess.Popen(["node", "frontend/server.mjs"], cwd=ROOT, env=env)
    react = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                urlopen(api_base + "/public-status", timeout=1)
                urlopen(react + "/health", timeout=1)
                break
            except Exception:
                time.sleep(0.1)
        joined = app.extensions  # noqa: F841
        from mielenosoitukset_fi.users.models import User  # noqa: F401
        friend = db.users.find_one({"_id": seeded_data["friend_id"]})
        perms = friend.get("global_permissions") or []
        db.users.update_one({"_id": seeded_data["friend_id"]},
                            {"$set": {"global_permissions": list(set(perms + ["TRANSLATE_DEMO"]))}})
        from tests.conftest import _client_for_user
        joined_client = _client_for_user(app, seeded_data["friend_id"])
        user_client.get("/")
        joined_client.get("/")

        meta, errors, buttons = {}, [], []

        def shoot(base, path, width, theme, name, client=None, full=False, js=True):
            ctx = playwright_browser.new_context(viewport={"width": width, "height": 900}, locale="fi-FI",
                                                 color_scheme=theme, java_script_enabled=js)
            if js:
                ctx.add_init_script(f"localStorage.setItem('theme', {json.dumps(theme)})")
            if client is not None:
                ctx.add_cookies([{"name": "session", "value": client.get_cookie("session").value, "url": base}])
            page = ctx.new_page()
            page.on("pageerror", lambda e: errors.append(f"{name}: {e}"))
            page.goto(base + path, wait_until="networkidle")
            page.evaluate("document.fonts.ready")
            file = OUT / f"{name}.png"
            if full:
                height = page.evaluate("Math.max(...[document.documentElement, document.body, ...document.querySelectorAll('body *')].map(e => e.scrollHeight - e.clientHeight + innerHeight))")
                page.set_viewport_size({"width": width, "height": height})
                page.wait_for_timeout(300)
            page.screenshot(path=str(file), animations="disabled")
            if name.startswith("after-translations") or name.startswith("after-upcoming"):
                buttons.append((name, page.evaluate("""() => [...document.querySelectorAll('.information-actions .button')].map(b => {
                    const s = getComputedStyle(b); return [b.tagName, b.getBoundingClientRect().height, s.fontSize, s.lineHeight, s.fontFamily.slice(0, 20), s.padding, s.borderWidth]; })""")))
            overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
            meta[file.name] = {"url": path, "width": width, "theme": theme, "full": full, "js": js,
                               "role": "anonymous" if client is None else ("joined" if client is joined_client else "signed-in"),
                               "overflow": overflow, "title": page.title(),
                               "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
            ctx.close()

        for path in PAGES:
            for width in (390, 1440):
                for theme in ("light", "dark"):
                    shoot(react, path, width, theme, f"after-{slug(path)}-{width}-{theme}")
                    shoot(react, path, width, theme, f"after-{slug(path)}-{width}-{theme}-full", full=True)
                shoot(live_server, path, width, "light", f"before-{slug(path)}-{width}-light-full", full=True)
        for width in (390, 1440):
            for label, client in (("signed-in", user_client), ("joined", joined_client)):
                shoot(react, "/upcoming/translations/", width, "light", f"after-translations-{label}-{width}-light", client=client)
            shoot(react, "/upcoming/translations/", width, "dark", f"after-translations-signed-in-{width}-dark", client=user_client)
            shoot(react, "/ohjeet", width, "light", f"after-ohjeet-nojs-{width}-light-full", full=True, js=False)
        (OUT / "meta.json").write_text(json.dumps({"images": meta, "errors": errors, "buttons": buttons}, indent=2))
    finally:
        host.terminate()
        host.wait(5)
        api.terminate()
        api.wait(5)


import pytest


@pytest.fixture
def playwright_browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
        yield browser
        browser.close()
