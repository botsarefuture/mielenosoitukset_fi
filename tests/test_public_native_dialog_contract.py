"""Keep public feedback inside the product UI instead of browser dialogs."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = ROOT / "mielenosoitukset_fi/templates"
STATIC_JS_ROOT = ROOT / "mielenosoitukset_fi/static/js"
EXCLUDED_TEMPLATE_TOP_LEVEL = {"admin", "admin_V2", "developer", "emails"}
NATIVE_DIALOG = re.compile(r"(?:\bwindow\s*\.\s*)?\b(?:alert|confirm|prompt)\s*\(")


def _active_public_templates():
    for template in sorted(TEMPLATE_ROOT.rglob("*.html")):
        relative = template.relative_to(TEMPLATE_ROOT)
        if relative.parts[0] not in EXCLUDED_TEMPLATE_TOP_LEVEL:
            yield template


def test_public_templates_do_not_use_native_browser_dialogs():
    offenders = []

    for template in _active_public_templates():
        if NATIVE_DIALOG.search(template.read_text(encoding="utf-8")):
            offenders.append(template.relative_to(ROOT).as_posix())

    assert offenders == [], (
        "Public templates must use shared feedback or modal components instead "
        f"of native browser dialogs: {offenders}"
    )


def test_shared_public_javascript_does_not_use_native_browser_dialogs():
    offenders = []

    for script in sorted(STATIC_JS_ROOT.glob("*.js")):
        if script.name.startswith("admin_"):
            continue
        if NATIVE_DIALOG.search(script.read_text(encoding="utf-8")):
            offenders.append(script.relative_to(ROOT).as_posix())

    assert offenders == [], (
        "Public JavaScript must use shared feedback or modal components instead "
        f"of native browser dialogs: {offenders}"
    )


def test_removed_legacy_scripts_cannot_be_reintroduced_or_referenced():
    removed_scripts = {"register.js", "deleteModal.js"}
    assert not any((STATIC_JS_ROOT / name).exists() for name in removed_scripts)

    references = []
    for template in sorted(TEMPLATE_ROOT.rglob("*.html")):
        source = template.read_text(encoding="utf-8")
        if any(name in source for name in removed_scripts):
            references.append(template.relative_to(ROOT).as_posix())

    assert references == []
