"""The banner-carrier call on the Pride page ships switched off and keeps its privacy promises."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "frontend" / "src" / "app"


def test_switch_is_a_single_boolean():
    data = json.loads((ROOT / "mielenosoitukset_fi" / "utils" / "data" / "pride_banner.json").read_text())
    assert list(data) == ["volunteer_form"] and isinstance(data["volunteer_form"], bool)


def test_screen_renders_the_call_only_behind_the_switch():
    screen = (APP / "PrideScreen.tsx").read_text()
    assert screen.count("{volunteers &&") == 2
    assert "const volunteers = prideVolunteerEnabled();" in screen


def test_form_asks_only_for_the_approved_fields():
    form = (APP / "PrideVolunteer.tsx").read_text()
    names = set(re.findall(r'name="(\w+)"', form))
    assert names == {"hp_trap", "name", "email", "city", "pride", "unsure", "note", "consent"}
    assert 'type="tel"' not in form


def test_copy_keeps_the_agreed_framing():
    copy = (APP / "pride-volunteer.ts").read_text()
    assert "Tarvitsemme kantajia jokaiseen Prideen" in copy
    assert "Ilmoittaudu banderollin kantajaksi" in copy
    assert "!" not in re.sub(r"=>|!==|!!", "", copy.split("export interface")[0].replace("'!", ""))
    for forbidden in ("rajallis", "emme voi luvata", "tulossa", "puhelinnumero:"):
        assert forbidden not in copy.lower().replace("emme kysy puhelinnumeroa", "")
