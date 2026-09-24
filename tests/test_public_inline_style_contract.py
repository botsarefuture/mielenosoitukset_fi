"""Prevent public templates from growing page-owned CSS debt.

The public UI modernization deliberately removes inline ``<style>`` blocks and
static ``style=`` attributes one page family at a time.  This snapshot makes
the remaining historical debt explicit: deleting an entry is welcome, while
adding or changing one requires a conscious baseline review instead of silently
creating another page-specific design system.
"""

from collections import Counter
import hashlib
import json
from pathlib import Path
import re


TEMPLATE_ROOT = Path("mielenosoitukset_fi/templates")
BASELINE_PATH = Path("tests/public_inline_style_baseline.json")
EXCLUDED_TOP_LEVEL = {"admin", "admin_V2", "developer", "emails"}


def _public_templates():
    for template in sorted(TEMPLATE_ROOT.rglob("*.html")):
        relative = template.relative_to(TEMPLATE_ROOT)
        if relative.parts[0] not in EXCLUDED_TOP_LEVEL:
            yield template, relative.as_posix()


def _short_hash(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _style_attribute_values(source):
    """Return style values in direct and script-generated HTML tags."""
    tag_pattern = re.compile(
        r'''<[A-Za-z][^"'<>]*(?:(?:"[^"]*"|'[^']*')[^"'<>]*)*>''',
        re.S,
    )
    style_pattern = re.compile(
        r'''(?<![-:\w])style\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))''',
        re.I | re.S,
    )
    values = []
    for tag in tag_pattern.findall(source):
        values.extend(
            next(value for value in match.groups() if value is not None)
            for match in style_pattern.finditer(tag)
        )
    return values


def _inline_style_snapshot():
    blocks = {}
    attributes = {}

    for template, relative in _public_templates():
        source = template.read_text(encoding="utf-8")
        style_blocks = re.findall(
            r"<style(?:\s[^>]*)?>(.*?)</style>", source, re.I | re.S
        )
        style_attributes = _style_attribute_values(source)

        if style_blocks:
            blocks[relative] = sorted(_short_hash(value) for value in style_blocks)
        if style_attributes:
            attributes[relative] = sorted(
                _short_hash(value) for value in style_attributes
            )

    return {"style_blocks": blocks, "style_attributes": attributes}


def _describe_difference(expected, actual):
    messages = []
    for category in ("style_blocks", "style_attributes"):
        paths = sorted(set(expected[category]) | set(actual[category]))
        for path in paths:
            expected_values = Counter(expected[category].get(path, []))
            actual_values = Counter(actual[category].get(path, []))
            added = list((actual_values - expected_values).elements())
            removed = list((expected_values - actual_values).elements())
            if added or removed:
                messages.append(
                    f"{category} {path}: added/changed={added}, removed={removed}"
                )
    return messages


def test_public_inline_style_debt_matches_reviewed_baseline():
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    actual = _inline_style_snapshot()
    differences = _describe_difference(baseline, actual)

    assert differences == [], (
        "Public inline-style debt changed:\n  "
        + "\n  ".join(differences)
        + "\nMove new or changed presentation into shared CSS. If historical inline "
        "styles were removed, shrink the reviewed baseline in the same PR."
    )


def test_public_inline_style_baseline_scope_is_documented():
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

    assert baseline["excluded_top_level"] == sorted(EXCLUDED_TOP_LEVEL)
    assert baseline["policy"] == "exact-reviewed-content-hashes"


def test_style_attribute_scanner_covers_all_valid_static_forms():
    source = """
        <div style="display: none"></div>
        <div style='color: red'></div>
        <div style=display:none></div>
        <div data-style=ignored></div>
        <script>const style = document.createElement("style");</script>
        <script>const row = `<div style=cursor:pointer></div>`;</script>
    """

    assert _style_attribute_values(source) == [
        "display: none",
        "color: red",
        "display:none",
        "cursor:pointer",
    ]
