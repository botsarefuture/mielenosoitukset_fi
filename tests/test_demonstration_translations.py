import importlib
import sys


class _FakeCollection:
    def find_one(self, *args, **kwargs):
        return None


class _FakeDB:
    def __getitem__(self, key):
        return _FakeCollection()


def _reset_demo_modules():
    for module_name in list(sys.modules):
        if module_name == "mielenosoitukset_fi.utils.classes" or module_name.startswith(
            "mielenosoitukset_fi.utils.classes."
        ):
            sys.modules.pop(module_name, None)


def _load_demonstration_class(monkeypatch):
    import mielenosoitukset_fi.utils.database as database_module

    monkeypatch.setattr(database_module, "get_database_manager", lambda: _FakeDB())
    _reset_demo_modules()

    module = importlib.import_module("mielenosoitukset_fi.utils.classes.Demonstration")
    return module.Demonstration


def teardown_module(module):
    _reset_demo_modules()


def _build_demo(Demonstration, **overrides):
    payload = {
        "title": "Suomenkielinen otsikko",
        "description": "Suomenkielinen kuvaus",
        "date": "2026-08-15",
        "start_time": "15:00",
        "end_time": "17:00",
        "city": "Helsinki",
        "address": "Testikatu 1",
        "tags": ["rauha", "testi"],
        "_dont_override": True,
    }
    payload.update(overrides)
    return Demonstration(**payload)


def test_demonstration_translation_falls_back_to_base_fields(monkeypatch):
    Demonstration = _load_demonstration_class(monkeypatch)

    demo = _build_demo(
        Demonstration,
        translations={
            "en": {
                "title": "English title",
            }
        }
    )

    assert demo.get_translation("en", "title") == "English title"
    assert demo.get_translation("en", "description") == "Suomenkielinen kuvaus"
    assert demo.get_translation("sv", "title") == "Suomenkielinen otsikko"
    assert demo.available_translation_languages() == ["en"]
    assert demo.get_localized_fields("en") == {
        "title": "English title",
        "description": "Suomenkielinen kuvaus",
        "tags": ["rauha", "testi"],
    }


def test_demonstration_translation_normalizes_tags_and_roundtrips_to_dict(monkeypatch):
    Demonstration = _load_demonstration_class(monkeypatch)

    demo = _build_demo(
        Demonstration,
        default_language="fi",
        translations={"en": {"tags": "peace, rally"}},
    )
    demo.set_translation("sv", "description", "Svensk beskrivning")

    data = demo.to_dict()
    restored = Demonstration.from_dict(data)

    assert data["default_language"] == "fi"
    assert data["translations"]["en"]["tags"] == ["peace", "rally"]
    assert restored.get_translation("en", "tags") == ["peace", "rally"]
    assert restored.get_translation("sv", "description") == "Svensk beskrivning"


def test_demo_localization_helper_supports_dict_payloads():
    from mielenosoitukset_fi.utils.demo_localization import (
        get_demo_localized_fields,
        get_demo_localized_value,
    )

    demo = {
        "title": "Suomenkielinen otsikko",
        "description": "Suomenkielinen kuvaus",
        "tags": ["rauha"],
        "default_language": "fi",
        "translations": {
            "en": {
                "title": "English title",
                "tags": ["peace"],
            }
        },
    }

    assert get_demo_localized_value(demo, "title", "en") == "English title"
    assert (
        get_demo_localized_value(demo, "description", "en")
        == "Suomenkielinen kuvaus"
    )
    assert get_demo_localized_value(demo, "title", "sv", fallback=False) is None
    assert get_demo_localized_fields(demo, "en") == {
        "title": "English title",
        "description": "Suomenkielinen kuvaus",
        "tags": ["peace"],
    }
