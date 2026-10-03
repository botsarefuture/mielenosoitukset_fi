from pathlib import Path
import re


CURRENT_TEMPLATE = Path(
    "mielenosoitukset_fi/templates/demo_views/calendar_grid.html"
)
LEGACY_TEMPLATE = Path(
    "mielenosoitukset_fi/templates/demo_views/calendar_grid_old.html"
)
CALENDAR_CSS = Path("mielenosoitukset_fi/static/css/public-calendar.css")


def _source(path):
    return path.read_text(encoding="utf-8")


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


def test_active_month_calendars_share_cache_keyed_static_styles():
    expected_link = (
        "url_for('static', filename='css/public-calendar.css', "
        "v='20261003-calendar-theme-1')"
    )

    for template, modifier in (
        (CURRENT_TEMPLATE, "public-calendar--current"),
        (LEGACY_TEMPLATE, "public-calendar--legacy"),
    ):
        source = _source(template)

        assert expected_link in source
        assert f'class="public-calendar {modifier}"' in source
        assert "<style" not in source
        assert not re.search(r"\sstyle\s*=", source, re.IGNORECASE)
        assert "jqueryui/1.13.2/jquery-ui.min.css" not in source


def test_calendar_styles_are_scoped_and_use_product_tokens():
    source = _source(CALENDAR_CSS)

    assert ".public-calendar .calendar-grid" in source
    assert ".public-calendar--current" in source
    assert ".public-calendar--legacy" in source
    assert "var(--product-action-bg)" in source
    assert "var(--product-on-action)" in source
    assert "var(--product-surface)" in source
    assert "var(--product-text)" in source
    assert "var(--product-border)" in source
    assert ":focus-visible" in source
    assert "@media (max-width: 768px)" in source
    assert "@media (prefers-reduced-motion: reduce)" in source
    assert "--pink-" not in source


def test_calendar_focus_ring_meets_non_text_contrast_in_both_themes():
    source = _source(CALENDAR_CSS)

    assert "outline: 3px solid var(--product-primary-strong);" in source
    assert _contrast_ratio("#00267a", "#f6f8fb") >= 3
    assert _contrast_ratio("#b9ceff", "#292f39") >= 3


def test_current_mobile_description_is_revealed_only_when_present():
    source = _source(CURRENT_TEMPLATE)

    assert 'class="mobile-demo-desc" hidden' in source
    assert "desc.hidden = false;" in source
    assert 'desc.style.display = "";' not in source
    assert ".public-calendar--current .mobile-demo-desc" not in _source(CALENDAR_CSS)


def test_legacy_view_switch_initializes_without_jquery():
    source = _source(LEGACY_TEMPLATE)
    switch_script = source.split('id="return-new-btn"', 1)[1].split(
        '<div class="mobile-list-view">', 1
    )[0]

    assert 'document.addEventListener("DOMContentLoaded"' in switch_script
    assert 'document.getElementById("return-new-btn")' in switch_script
    assert 'returnButton.addEventListener("click"' in switch_script
    assert "$(" not in switch_script
    assert 'document.cookie = "old-calendar-view=false;' in switch_script
