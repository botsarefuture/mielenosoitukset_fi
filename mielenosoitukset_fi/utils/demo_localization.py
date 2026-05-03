import copy


TRANSLATABLE_DEMO_FIELDS = ("title", "description", "tags")


def normalize_demo_language(language: str, default: str = "fi") -> str:
    normalized = (language or "").strip().lower()
    fallback = (default or "fi").strip().lower()
    return normalized or fallback or "fi"


def get_demo_localized_value(
    demo, field: str, language: str = None, fallback: bool = True
):
    if field not in TRANSLATABLE_DEMO_FIELDS:
        raise ValueError(f"Unsupported translatable field: {field}")

    if hasattr(demo, "get_translation"):
        return demo.get_translation(language, field, fallback=fallback)

    if not isinstance(demo, dict):
        raise TypeError("demo must be a Demonstration instance or a dict")

    normalized_language = normalize_demo_language(
        language, demo.get("default_language", "fi")
    )
    translations = demo.get("translations") or {}
    translated = translations.get(normalized_language, {}).get(field)

    if translated not in (None, "", []):
        return copy.deepcopy(translated)

    if fallback:
        return copy.deepcopy(demo.get(field))

    return [] if field == "tags" else None


def get_demo_localized_fields(demo, language: str = None, fallback: bool = True):
    return {
        "title": get_demo_localized_value(demo, "title", language, fallback=fallback),
        "description": get_demo_localized_value(
            demo, "description", language, fallback=fallback
        ),
        "tags": get_demo_localized_value(demo, "tags", language, fallback=fallback),
    }
