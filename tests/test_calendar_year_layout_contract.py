from pathlib import Path
import re


YEAR_TEMPLATE = Path("mielenosoitukset_fi/templates/demo_views/calendar_year.html")
YEAR_STYLES = Path("mielenosoitukset_fi/static/css/calendar-year.css")


def _relative_luminance(hex_color):
    channels = [int(hex_color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92
        if channel <= 0.04045
        else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(first, second):
    lighter, darker = sorted(
        (_relative_luminance(first), _relative_luminance(second)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


def test_calendar_year_uses_versioned_scoped_styles_without_inline_debt():
    template = YEAR_TEMPLATE.read_text(encoding="utf-8")

    assert "filename='css/calendar-year.css'" in template
    assert "v='20261004-calendar-year-1'" in template
    assert "<style" not in template.lower()
    assert re.search(r"\sstyle\s*=", template, flags=re.IGNORECASE) is None
    assert "cdnjs.cloudflare.com/ajax/libs/jqueryui" not in template
    assert 'class="calendar-year-page"' in template


def test_calendar_year_styles_follow_product_theme_and_accessibility_contract():
    styles = YEAR_STYLES.read_text(encoding="utf-8")

    assert ":root" not in styles
    assert "--pink-" not in styles
    assert re.search(r"#[0-9a-fA-F]{3,8}\b", styles) is None
    assert "var(--product-surface)" in styles
    assert "var(--product-text)" in styles
    assert "var(--product-action-bg)" in styles
    assert ":focus-visible" in styles
    assert "@media (prefers-reduced-motion: reduce)" in styles
    assert "@media (max-width: 1100px) and (min-width: 769px)" in styles
    assert "@media (max-width: 768px)" in styles


def test_calendar_year_focus_indicators_contrast_with_their_surfaces():
    styles = YEAR_STYLES.read_text(encoding="utf-8")

    assert ".mobile-month-link:focus-visible" in styles
    assert "outline-color: var(--product-on-action);" in styles
    assert _contrast_ratio("#ffffff", "#0033a0") >= 3
    assert _contrast_ratio("#ffffff", "#416fbd") >= 3
    assert _contrast_ratio("#9c3b00", "#f6f8fb") >= 3
    assert _contrast_ratio("#ffb078", "#292f39") >= 3


def test_calendar_year_keeps_behavioral_hooks_and_respects_reduced_motion():
    template = YEAR_TEMPLATE.read_text(encoding="utf-8")

    for hook in (
        'id="calendar-onboarding"',
        'class="onboarding-tooltip"',
        'class="onboarding-next"',
        'class="demo-cell"',
        'id="demo-preview"',
        "selector: '.calendar-year-nav'",
        "selector: '.year-calendar a'",
        "selector: '.demo-cell:first'",
    ):
        assert hook in template

    assert "window.matchMedia('(prefers-reduced-motion: reduce)')" in template
    assert "preview.html(html)" in template
