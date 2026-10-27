"""Opt-in local pytest capture hook for the real demonstration submit screen.

Reuses existing Flask/Mongo/browser fixtures and actual application assets. It
never supplies a visual verdict and is not loaded by the normal test suite.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
from urllib.parse import urlparse

import pytest

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_HOSTS = {
    "localhost", "127.0.0.1", "cdn2.mielenosoitukset.fi", "fonts.googleapis.com",
    "fonts.gstatic.com", "cdn.socket.io", "cdn.jsdelivr.net", "cdn.quilljs.com",
    "cdn.ckeditor.com", "code.jquery.com",
}


def source_inputs() -> dict:
    """Hash actual changed/untracked sources and relevant shared rendered inputs."""
    def git(*args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()

    names = set(filter(None, git("diff", "--name-only", "-z", "HEAD").split("\0")))
    names.update(filter(None, git("ls-files", "--others", "--exclude-standard", "-z").split("\0")))
    names.update(filter(None, git("ls-files", "-z", "--", "frontend", "mielenosoitukset_fi/static/frontend").split("\0")))
    names.update({
        "tests/conftest.py", "config.py", "mielenosoitukset_fi/app.py",
        "mielenosoitukset_fi/basic_routes.py", "mielenosoitukset_fi/templates/base.html",
        "mielenosoitukset_fi/templates/submit.html", "mielenosoitukset_fi/templates/paikkakunta-dropdown.html",
        "mielenosoitukset_fi/static/css/product-tokens.css", "mielenosoitukset_fi/static/css/user-workspace.css",
        "mielenosoitukset_fi/static/css/submit.css", "mielenosoitukset_fi/static/css/public-header.css",
        "mielenosoitukset_fi/static/js/submit-draft.js", "scripts/verify_submit_form.py",
        "scripts/submit_visual_capture.py",
    })
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
              if (ROOT / name).is_file() else "DELETED" for name in sorted(names)}
    return {"head": git("rev-parse", "HEAD"), "worktree": str(ROOT), "files": hashes,
            "sha256": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()}


def capture(item) -> None:
    output = Path(os.environ["MOSO_SUBMIT_CAPTURE_DIR"]).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    stage = os.environ.get("MOSO_SUBMIT_CAPTURE_STAGE", "final")
    request = item._request
    request.getfixturevalue("seeded_data")
    base = request.getfixturevalue("live_server")
    browser = request.getfixturevalue("playwright_browser")
    images, image_hashes, image_states, errors, failed, responses = [], {}, {}, [], [], []
    before = source_inputs()

    def assets(route):
        if urlparse(route.request.url).scheme in {"blob", "data", "about"} or urlparse(route.request.url).hostname in ALLOWED_HOSTS:
            route.continue_()
        else:
            route.abort()

    def shot(page, name, target=None):
        if target:
            page.locator(target).first.evaluate("e => window.scrollTo({top:Math.max(0,e.getBoundingClientRect().top+scrollY-100),behavior:'instant'})")
            page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
        page.evaluate("document.fonts.ready")
        page.evaluate("() => Promise.all(document.getAnimations().filter(a => a.effect?.getTiming().iterations !== Infinity).map(a => a.finished.catch(() => {})))")
        filename = f"{stage}-{name}.png"
        path = output / filename
        page.screenshot(path=str(path), animations="disabled")
        images.append(filename)
        image_hashes[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
        image_states[filename] = {
            "viewport": page.viewport_size, "locale": page.locator("html").get_attribute("lang"),
            "theme": "dark" if "dark" in (page.locator("html").get_attribute("class") or "") else "light",
            "role": "anonymous", "state": name,
        }
        if stage == "final":
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), filename

    def perform_captures():
        for width in (390, 1440):
            for theme in ("light", "dark"):
                context = browser.new_context(viewport={"width": width, "height": 1000},
                                              locale="fi-FI", color_scheme=theme)
                context.route("**/*", assets)
                context.add_init_script(f"localStorage.setItem('theme', {json.dumps(theme)})")
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("requestfailed", lambda req: failed.append(req.url))
                page.on("response", lambda response: responses.append({"url": response.url, "status": response.status}) if response.status >= 400 else None)
                try:
                    page.goto(base + "/submit", wait_until="networkidle")
                    page.locator("#page-1.active").wait_for(state="visible")
                    page.wait_for_function("() => typeof window.saveSubmitDraft === 'function'")
                    # Real editor, rather than a Quill substitute, is required here.
                    page.locator(".ql-editor").wait_for(state="attached")
                    shot(page, f"initial-{width}-{theme}")
                    page.evaluate("chooseManual()")
                    page.locator("#page-2.active").wait_for(state="visible")
                    shot(page, f"basics-{width}-{theme}", "#page-2")
                    if stage == "final":
                        for step, name in ((3, "location"), (4, "organizers"), (5, "contacts"), (6, "success")):
                            page.evaluate("step => showPage(step)", step)
                            page.locator(f"#page-{step}.active").wait_for(state="visible")
                            shot(page, f"{name}-{width}-{theme}", f"#page-{step}")
                finally:
                    context.close()
        if stage == "final":
            for width, theme in ((1440, "light"), (390, "dark")):
                context = browser.new_context(viewport={"width": width, "height": 1000},
                                              locale="fi-FI", color_scheme=theme)
                context.route("**/*", assets)
                context.add_init_script(f"localStorage.setItem('theme', {json.dumps(theme)})")
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("requestfailed", lambda req: failed.append(req.url))
                try:
                    page.goto(base + "/submit", wait_until="networkidle")
                    page.wait_for_function("() => typeof window.saveSubmitDraft === 'function'")
                    page.locator("#page-1 button").filter(has_text="Lisää tiedot itse").click()
                    page.locator("#page-2.active").wait_for(state="visible")
                    page.locator("#page-2 .form-navigation button").last.click()
                    assert page.locator("#name").get_attribute("aria-invalid") == "true"
                    shot(page, f"invalid-{width}-{theme}", "#submit-feedback")
                    page.locator("#name").fill("Yhdessä oikeudenmukaisen ja kestävän tulevaisuuden puolesta")
                    page.locator("#tags").fill("ilmasto, oikeudenmukaisuus")
                    page.locator(".ql-editor").fill("Kokoonnumme rauhanomaisesti Kansalaistorille. Kaikki ovat tervetulleita osallistumaan.")
                    page.locator("#image").set_input_files(str(ROOT / "mielenosoitukset_fi/static/kampanja/og-banner.png"))
                    page.locator("#cropperModal").wait_for(state="visible")
                    page.wait_for_function("() => !document.querySelector('#applyCrop').disabled")
                    shot(page, f"cropper-{width}-{theme}")
                    page.locator("#applyCrop").click()
                    page.locator("#cropperModal").wait_for(state="hidden")
                    page.wait_for_function("() => {const i=document.querySelector('#image-preview'); return i?.complete && i.naturalWidth>0;}")
                    shot(page, f"editor-image-{width}-{theme}", "#editor")
                    page.locator("#page-2 .form-navigation button").last.click()
                    page.locator("#page-3.active").wait_for(state="visible")
                    page.locator("#date").evaluate("e => e._flatpickr.open()")
                    shot(page, f"calendar-{width}-{theme}", ".flatpickr-calendar.open")
                    page.locator("#date").evaluate("e => e._flatpickr.close()")
                    page.evaluate("""() => {
                        document.querySelector('#date')._flatpickr.setDate('2027-11-01', true);
                        document.querySelector('#start_time')._flatpickr.setDate('12:00', true);
                    }""")
                    page.locator("#type").select_option("marssi")
                    page.locator("#route").fill("Kansalaistori, Mannerheimintie, Eduskuntatalo")
                    page.locator(".dropbtn").click()
                    page.locator("#searchInput").fill("Helsinki")
                    shot(page, f"municipality-{width}-{theme}", "#paikkakunta-drop")
                    page.locator("#dropdown-content [role=option]").filter(has_text="Helsinki").first.click()
                    page.locator("#address").fill("Kansalaistori")
                    page.locator("#page-3 .form-navigation button").last.click()
                    page.locator("#page-4.active").wait_for(state="visible")
                    page.locator("#organizer_name_1").fill("Esimerkkijärjestö kestävän tulevaisuuden puolesta")
                    page.locator("#organizer_email_1").fill("organizer@example.test")
                    page.locator("#page-4 .form-navigation button").last.click()
                    page.locator("#page-5.active").wait_for(state="visible")
                    page.locator("#submitter_role").fill("Järjestäjä")
                    page.locator("#submitter_name").fill("Esimerkki Ilmoittaja")
                    page.locator("#submitter_email").fill("submitter@example.test")
                    page.locator("#accept_terms").check()
                    page.evaluate("window.dispatchEvent(new Event('pagehide'))")
                    page.wait_for_function("() => JSON.parse(localStorage.getItem('mielenosoitukset.submit-draft.v2') || '{}').fields?.submitter_email === 'submitter@example.test'")
                    page.reload(wait_until="networkidle")
                    page.locator("#cacheNotice").wait_for(state="visible")
                    assert page.locator("#name").input_value().startswith("Yhdessä")
                    assert page.locator("#accept_terms").is_checked() is False
                    shot(page, f"restored-draft-{width}-{theme}", "#cacheNotice")
                    page.locator("#page-5.active").wait_for(state="visible")
                    page.locator("#accept_terms").check()
                    calls = []

                    def submission(route):
                        calls.append(route.request.post_data)
                        route.fulfill(status=409, content_type="application/json", body=json.dumps({
                            "success": False, "conflict": True,
                            "message": "Samalle päivälle löytyi samankaltainen mielenosoitusilmoitus.",
                            "demos": [{"title": "Yhdessä oikeudenmukaisen ja kestävän tulevaisuuden puolesta", "date": "2027-11-01", "address": "Kansalaistori"}],
                        }))

                    page.route("**/submit", submission)
                    page.locator("#submit-form").click()
                    page.locator("#submitConflictModal").wait_for(state="visible")
                    shot(page, f"conflict-{width}-{theme}")
                    page.locator("#submit-conflict-cancel").click()
                    page.locator("#submitConflictModal").wait_for(state="hidden")
                    assert len(calls) == 1
                    assert page.locator("#name").input_value().startswith("Yhdessä")
                finally:
                    context.close()
    failure = None
    try:
        perform_captures()
    except Exception as error:
        failure = {"type": type(error).__name__, "message": str(error)}
    after = source_inputs()
    if before != after:
        failure = failure or {"type": "AssertionError", "message": "Source changed during capture. Rerun with a stable checkout."}
    metadata = {
        "run_id": os.environ.get("MOSO_SUBMIT_CAPTURE_RUN"), "stage": stage,
        "completed": failure is None, "failure": failure,
        "images": images, "image_hashes": image_hashes, "image_states": image_states,
        "errors": errors, "failed": sorted(set(failed)), "http_errors": responses,
        "source_inputs": after, "runtime": {"python": platform.python_version()},
        "notes": ["Real Flask page and disposable test database; actual styles, fonts and Quill assets.",
                  "External analytics blocked; no real event submitted. Success is a presentation-only wizard state; duplicate response is deliberately intercepted for the modal capture.",
                  "Image upload preview uses the repository og-banner.png fixture. Actual editor/navigation/draft controls exercised with synthetic contact values."],
    }
    (output / f"{stage}-metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    if failure:
        raise AssertionError(f"Incomplete capture: {failure['type']}: {failure['message']}")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    result = yield
    if result.excinfo is None:
        capture(item)
