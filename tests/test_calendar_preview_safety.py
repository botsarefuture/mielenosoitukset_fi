import re
from pathlib import Path

import pytest


TEMPLATE_PATHS = (
    Path("mielenosoitukset_fi/templates/demo_views/calendar_grid.html"),
    Path("mielenosoitukset_fi/templates/demo_views/calendar_grid_old.html"),
    Path("mielenosoitukset_fi/templates/demo_views/calendar_year.html"),
)
HELPER_PATH = Path("mielenosoitukset_fi/static/js/calendar-preview.js")
VERSIONED_HELPER_INCLUDE = (
    "url_for('static', filename='js/calendar-preview.js', "
    "v='20261004-calendar-preview-1')"
)


def test_calendar_templates_use_shared_safe_hover_preview_renderer():
    for path in TEMPLATE_PATHS:
        source = path.read_text(encoding="utf-8")

        assert VERSIONED_HELPER_INCLUDE in source, path
        assert "window.CalendarPreview.render(preview[0]" in source, path
        assert re.search(r"\.html\s*\(", source) is None, path
        assert "innerHTML" not in source, path


def test_calendar_mobile_descriptions_are_not_marked_as_html():
    current_source = TEMPLATE_PATHS[0].read_text(encoding="utf-8")
    legacy_source = TEMPLATE_PATHS[1].read_text(encoding="utf-8")
    year_source = TEMPLATE_PATHS[2].read_text(encoding="utf-8")

    assert "desc.textContent = tex" in current_source
    assert "demo.description[:100]|safe" not in legacy_source
    assert "demo.description[:80]|e|safe" not in year_source


def test_calendar_preview_helper_only_builds_text_dom_nodes():
    source = HELPER_PATH.read_text(encoding="utf-8")

    assert 'document.createElement("img")' in source
    assert 'document.createElement("strong")' in source
    assert 'document.createElement("p")' in source
    assert ".textContent" in source
    assert "replaceChildren(" in source
    assert "innerHTML" not in source
    assert re.search(r"\.html\s*\(", source) is None


@pytest.mark.e2e
def test_calendar_preview_renders_untrusted_values_as_text_in_browser(browser_page):
    payload = '<img src=x onerror="window.calendarPreviewExecuted=true">'

    browser_page.set_content('<div id="preview"></div>')
    browser_page.add_script_tag(path=str(HELPER_PATH.resolve()))
    browser_page.add_script_tag(
        type="module",
        content=(
            "window.calendarPreviewModuleReady = "
            "typeof window.CalendarPreview.render === 'function';"
        ),
    )
    browser_page.wait_for_function("window.calendarPreviewModuleReady === true")

    rendered = browser_page.evaluate(
        """
        ({ payload }) => {
          const preview = document.getElementById("preview");
          window.CalendarPreview.render(preview, {
            title: payload,
            description: payload,
            imageUrl: "/preview.png",
          });
          return {
            tags: [...preview.children].map((node) => node.tagName),
            title: preview.children[1].textContent,
            description: preview.children[2].textContent,
            imageSrc: preview.children[0].getAttribute("src"),
            imageAlt: preview.children[0].getAttribute("alt"),
            executed: Boolean(window.calendarPreviewExecuted),
          };
        }
        """,
        {"payload": payload},
    )

    assert rendered == {
        "tags": ["IMG", "STRONG", "P"],
        "title": payload,
        "description": payload,
        "imageSrc": "/preview.png",
        "imageAlt": payload,
        "executed": False,
    }

    optional_nodes = browser_page.evaluate(
        """
        () => {
          const preview = document.getElementById("preview");
          window.CalendarPreview.render(preview, {
            title: "Only a title",
            description: "",
            imageUrl: "",
          });
          return [...preview.children].map((node) => node.tagName);
        }
        """
    )
    assert optional_nodes == ["STRONG"]
