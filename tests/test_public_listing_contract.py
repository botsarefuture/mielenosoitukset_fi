from pathlib import Path


TEMPLATE_ROOT = Path("mielenosoitukset_fi/templates")
CSS_PATH = Path("mielenosoitukset_fi/static/css/user-workspace.css")
JS_PATH = Path("mielenosoitukset_fi/static/js/user-pagination.js")


def test_public_listing_family_uses_shared_hero_and_pagination_markup():
    list_template = (TEMPLATE_ROOT / "list.html").read_text(encoding="utf-8")
    city_template = (TEMPLATE_ROOT / "city.html").read_text(encoding="utf-8")
    tag_template = (TEMPLATE_ROOT / "tag_list.html").read_text(encoding="utf-8")

    assert "from '_macros/_hero.html' import hero_section" in list_template
    assert "from '_macros/_hero.html' import hero_section" in city_template
    assert "from '_macros/_hero.html' import hero_section" in tag_template
    assert "load_more_button()" in list_template
    assert "load_more_button()" in city_template
    assert "load_more_button()" in tag_template
    assert "listing_end_message()" not in city_template


def test_public_listing_pagination_controller_supports_buttons_and_sentinels():
    source = JS_PATH.read_text(encoding="utf-8")

    assert "sentinel = null" in source
    assert "new IntersectionObserver" in source
    assert "button.hidden = currentPage >= totalPages" in source
    assert "async function reload" in source


def test_public_workspace_styles_cover_listing_end_message():
    stylesheet = CSS_PATH.read_text(encoding="utf-8")

    assert ".end-of-content-message" in stylesheet
    assert ".end-of-content-message[hidden]" in stylesheet
