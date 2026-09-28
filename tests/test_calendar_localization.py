import json
from pathlib import Path

import pytest
from babel.messages import pofile


ROUTES = Path("mielenosoitukset_fi/basic_routes.py")
MONTH_TEMPLATE = Path("mielenosoitukset_fi/templates/demo_views/calendar_grid.html")
OLD_MONTH_TEMPLATE = Path(
    "mielenosoitukset_fi/templates/demo_views/calendar_grid_old.html"
)
YEAR_TEMPLATE = Path("mielenosoitukset_fi/templates/demo_views/calendar_year.html")

CALENDAR_LABELS = {
    "Edellinen",
    "Seuraava",
    "Vuosi",
    "Ei otsikkoa",
    "tapahtuma",
    "tapahtumaa",
    "Palaa vanhaan näkymään",
    "Palaa uuteen näkymään",
    "Ei tapahtumia tässä kuussa",
    "Kalenteri %(year)s",
    "Edellinen vuosi",
    "Seuraava vuosi",
    "Tapahtumaa",
    "Kuukautta",
    "Näytä kuukausinäkymä",
    "Vuosinavigaatio",
    "Kuukausilinkit",
}


def _set_locale(app, client, locale):
    app.config["BABEL_PUBLIC_LOCALES"] = ["fi", "en", "sv"]
    with client.session_transaction() as session:
        session["locale"] = locale


def test_calendar_routes_use_babel_locale_data_instead_of_finnish_maps():
    source = ROUTES.read_text(encoding="utf-8")
    calendar_section = source.split("def _localized_calendar_labels", 1)[1].split(
        "def report_malicious", 1
    )[0]

    assert "babel_format_date" in calendar_section
    assert "get_day_names" in calendar_section
    assert "calendar_locale=calendar_locale" in calendar_section
    assert "weekday_names=weekday_names" in calendar_section
    for month_name in ("Tammikuu", "Helmikuu", "Maaliskuu", "Joulukuu"):
        assert month_name not in calendar_section


def test_calendar_templates_share_locale_and_fallback_contracts():
    month_source = MONTH_TEMPLATE.read_text(encoding="utf-8")
    old_source = OLD_MONTH_TEMPLATE.read_text(encoding="utf-8")
    year_source = YEAR_TEMPLATE.read_text(encoding="utf-8")

    for source in (month_source, old_source, year_source):
        assert "{% for weekday_name in weekday_names %}" in source
        assert "demo.title|e or _('Ei otsikkoa')" in source
        assert "<th>Ma</th>" not in source

    assert "locale: {{ calendar_locale | tojson }}" in month_source
    assert "toLocaleDateString(calendarI18n.locale" in month_source
    assert 'toLocaleDateString("FI-fi")' not in month_source
    assert "ISO8001toFinnish" not in month_source


def test_calendar_labels_have_english_and_swedish_translations():
    for locale in ("en", "sv"):
        path = Path(
            f"mielenosoitukset_fi/translations/{locale}/LC_MESSAGES/messages.po"
        )
        with path.open(encoding="utf-8") as catalog_file:
            catalog = pofile.read_po(catalog_file)

        for message_id in CALENDAR_LABELS:
            message = catalog.get(message_id)
            assert message is not None, (locale, message_id)
            assert message.string, (locale, message_id)


@pytest.mark.parametrize(
    ("locale", "month_name", "previous", "next_label", "year_label", "weekday"),
    [
        ("en", "January", "Previous", "Next", "Year", "Mon"),
        ("sv", "januari", "Föregående", "Nästa", "År", "mån"),
    ],
)
def test_current_and_legacy_month_views_render_active_locale(
    app,
    client,
    locale,
    month_name,
    previous,
    next_label,
    year_label,
    weekday,
):
    _set_locale(app, client, locale)

    current_response = client.get("/calendar/2030/1/")
    assert current_response.status_code == 200
    current_body = current_response.get_data(as_text=True)
    for text in (month_name, previous, next_label, year_label, weekday):
        assert text in current_body

    client.set_cookie("old-calendar-view", "true")
    legacy_response = client.get("/calendar/2030/1/")
    assert legacy_response.status_code == 200
    legacy_body = legacy_response.get_data(as_text=True)
    for text in (month_name, previous, next_label, year_label, weekday):
        assert text in legacy_body


@pytest.mark.parametrize(
    ("locale", "month_name", "previous_year", "next_year", "onboarding"),
    [
        ("en", "January", "Previous year", "Next year", "Year navigation"),
        ("sv", "januari", "Föregående år", "Nästa år", "Årsnavigering"),
    ],
)
def test_year_view_renders_active_locale(
    app, client, locale, month_name, previous_year, next_year, onboarding
):
    _set_locale(app, client, locale)

    response = client.get("/calendar/2030/")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    for text in (month_name, previous_year, next_year):
        assert text in body
    assert json.dumps(onboarding) in body
