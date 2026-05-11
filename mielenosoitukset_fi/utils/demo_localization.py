import copy
import re


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


def get_demo_available_languages(demo):
    if hasattr(demo, "available_languages"):
        return demo.available_languages()

    if not isinstance(demo, dict):
        raise TypeError("demo must be a Demonstration instance or a dict")

    languages = set()
    default_language = normalize_demo_language(demo.get("default_language", "fi"))
    if default_language:
        languages.add(default_language)

    translations = demo.get("translations") or {}
    for language, values in translations.items():
        if not isinstance(values, dict):
            continue
        normalized = normalize_demo_language(language, default_language)
        if values:
            languages.add(normalized)

    return sorted(languages)


def get_demo_localized_dict(
    demo,
    language: str = None,
    fallback: bool = True,
    include_translations: bool = True,
):
    if hasattr(demo, "to_localized_dict"):
        return demo.to_localized_dict(
            language=language,
            fallback=fallback,
            include_translations=include_translations,
        )

    if not isinstance(demo, dict):
        raise TypeError("demo must be a Demonstration instance or a dict")

    data = copy.deepcopy(demo)
    data.update(get_demo_localized_fields(demo, language=language, fallback=fallback))
    data["resolved_language"] = normalize_demo_language(
        language, demo.get("default_language", "fi")
    )
    data["available_languages"] = get_demo_available_languages(demo)

    if not include_translations:
        data.pop("translations", None)

    return data


def _iter_demo_searchable_texts(demo):
    if hasattr(demo, "to_dict"):
        demo = demo.to_dict(json=False)

    if not isinstance(demo, dict):
        raise TypeError("demo must be a Demonstration instance or a dict")

    values = []
    for field in ("title", "description", "address", "city"):
        value = demo.get(field)
        if value:
            values.append(str(value))

    for tag in demo.get("tags") or []:
        if tag:
            values.append(str(tag))

    translations = demo.get("translations") or {}
    for localized_values in translations.values():
        if not isinstance(localized_values, dict):
            continue
        for field in ("title", "description"):
            value = localized_values.get(field)
            if value:
                values.append(str(value))
        for tag in localized_values.get("tags") or []:
            if tag:
                values.append(str(tag))

    return values


def demo_matches_search_query(demo, search_query: str) -> bool:
    normalized_query = (search_query or "").strip().casefold()
    if not normalized_query:
        return True

    return any(
        normalized_query in text.casefold()
        for text in _iter_demo_searchable_texts(demo)
    )


def demo_has_tag(demo, tag_query: str) -> bool:
    normalized_tag = (tag_query or "").strip().casefold()
    if not normalized_tag:
        return True

    if hasattr(demo, "to_dict"):
        demo = demo.to_dict(json=False)

    if not isinstance(demo, dict):
        raise TypeError("demo must be a Demonstration instance or a dict")

    base_tags = [str(tag).strip().casefold() for tag in demo.get("tags") or [] if str(tag).strip()]
    if normalized_tag in base_tags:
        return True

    translations = demo.get("translations") or {}
    for localized_values in translations.values():
        if not isinstance(localized_values, dict):
            continue
        translated_tags = [
            str(tag).strip().casefold()
            for tag in localized_values.get("tags") or []
            if str(tag).strip()
        ]
        if normalized_tag in translated_tags:
            return True

    return False


def demo_matches_title_query(demo, title_query: str) -> bool:
    normalized_query = (title_query or "").strip().casefold()
    if not normalized_query:
        return True

    if hasattr(demo, "to_dict"):
        demo = demo.to_dict(json=False)

    if not isinstance(demo, dict):
        raise TypeError("demo must be a Demonstration instance or a dict")

    candidates = []
    base_title = demo.get("title")
    if base_title:
        candidates.append(str(base_title))

    translations = demo.get("translations") or {}
    for localized_values in translations.values():
        if not isinstance(localized_values, dict):
            continue
        translated_title = localized_values.get("title")
        if translated_title:
            candidates.append(str(translated_title))

    return any(normalized_query in candidate.casefold() for candidate in candidates)


def demo_title_candidates(demo):
    if hasattr(demo, "to_dict"):
        demo = demo.to_dict(json=False)

    if not isinstance(demo, dict):
        raise TypeError("demo must be a Demonstration instance or a dict")

    candidates = []
    base_title = demo.get("title")
    if base_title:
        candidates.append(str(base_title))

    translations = demo.get("translations") or {}
    for localized_values in translations.values():
        if not isinstance(localized_values, dict):
            continue
        translated_title = localized_values.get("title")
        if translated_title:
            candidates.append(str(translated_title))

    return candidates


def demo_matches_conflict_candidate(demo, submitted_title: str, submitted_address: str = "") -> bool:
    normalized_title = (submitted_title or "").strip().casefold()
    normalized_address = (submitted_address or "").strip().casefold()
    if not normalized_title:
        return False

    title_words = {
        word for word in re.findall(r"\w+", normalized_title) if len(word) > 3
    }

    for candidate_title in demo_title_candidates(demo):
        existing_title = candidate_title.casefold()
        if normalized_title in existing_title or existing_title in normalized_title:
            return True

        existing_words = {
            word for word in re.findall(r"\w+", existing_title) if len(word) > 3
        }
        if title_words and len(title_words & existing_words) >= 2:
            return True

    if normalized_address:
        existing_addr = str((demo.get("address") if isinstance(demo, dict) else "") or "").casefold()
        if existing_addr and (
            normalized_address in existing_addr or existing_addr in normalized_address
        ):
            return True

    return False
