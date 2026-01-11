from typing import Iterable, Dict, Optional


def _normalize_lang(lang: Optional[str]) -> str:
    return (lang or "").strip().lower()


def normalize_translation_languages(
    languages: Iterable[str], supported_locales: Iterable[str], primary_language: Optional[str] = None
) -> list[str]:
    supported = {_normalize_lang(lang) for lang in (supported_locales or []) if lang}
    primary = _normalize_lang(primary_language)
    normalized = []
    for lang in languages or []:
        code = _normalize_lang(lang)
        if not code or code not in supported:
            continue
        if primary and code == primary:
            continue
        if code not in normalized:
            normalized.append(code)
    return normalized


def build_translation_payload(
    form,
    languages: Iterable[str],
    title_prefix: str = "translation_title_",
    description_prefix: str = "translation_description_",
    tags_prefix: str = "translation_tags_",
) -> Dict[str, Dict[str, str]]:
    translations: Dict[str, Dict[str, str]] = {}
    for lang in languages or []:
        title = (form.get(f"{title_prefix}{lang}") or "").strip()
        description = (form.get(f"{description_prefix}{lang}") or "").strip()
        tags_value = (form.get(f"{tags_prefix}{lang}") or "").strip()
        tags = [tag.strip() for tag in tags_value.split(",") if tag.strip()] if tags_value else []
        if not title and not description and not tags:
            continue
        payload: Dict[str, str] = {}
        if title:
            payload["title"] = title
        if description:
            payload["description"] = description
        if tags:
            payload["tags"] = tags
        translations[lang] = payload
    return translations


def apply_demo_translation(demo: dict, locale: Optional[str], default_locale: Optional[str] = None) -> dict:
    if not demo or not isinstance(demo, dict):
        return demo
    normalized_locale = _normalize_lang(locale)
    if not normalized_locale:
        return demo
    translations = demo.get("translations") or {}
    primary_language = _normalize_lang(demo.get("primary_language") or default_locale)
    if primary_language and normalized_locale == primary_language:
        return demo
    localized = translations.get(normalized_locale) or {}
    if not localized and default_locale:
        fallback = _normalize_lang(default_locale)
        if fallback and fallback != normalized_locale:
            localized = translations.get(fallback) or {}
    if localized:
        title = localized.get("title")
        description = localized.get("description")
        tags = localized.get("tags")
        if title:
            demo["title"] = title
        if description:
            demo["description"] = description
        if tags:
            demo["tags"] = tags
    return demo
