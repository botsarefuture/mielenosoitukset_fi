from __future__ import annotations

from typing import Dict, Iterable

import requests

from config import Config


DEEPL_DEFAULT_API_URL = "https://api-free.deepl.com/v2/translate"
TRANSLATABLE_FIELDS = ("title", "description", "tags")


def _normalize_locale(locale: str) -> str:
    return (locale or "").strip().lower()


def _deepl_language_code(locale: str) -> str:
    normalized = _normalize_locale(locale)
    mapping = {
        "en": "EN",
        "fi": "FI",
        "sv": "SV",
        "de": "DE",
        "fr": "FR",
        "et": "ET",
    }
    return mapping.get(normalized, normalized.upper())


def _stringify_field_value(field: str, value):
    if field == "tags":
        if not value:
            return ""
        if isinstance(value, str):
            return value
        return ", ".join(str(tag).strip() for tag in value if str(tag).strip())
    return str(value or "")


def _parse_translated_field_value(field: str, value: str):
    if field == "tags":
        return [tag.strip() for tag in (value or "").split(",") if tag.strip()]
    return (value or "").strip()


def deepl_is_configured() -> bool:
    return bool(getattr(Config, "DEEPL_API_KEY", ""))


def build_deepl_translation_suggestions(
    source_fields: Dict[str, object],
    source_language: str,
    target_languages: Iterable[str],
    *,
    timeout: int = 15,
) -> Dict[str, dict]:
    if not deepl_is_configured():
        raise RuntimeError("DeepL API key is not configured")

    api_url = getattr(Config, "DEEPL_API_URL", "") or DEEPL_DEFAULT_API_URL
    normalized_source = _normalize_locale(source_language) or "fi"
    suggestions = {}

    for target_language in target_languages:
        normalized_target = _normalize_locale(target_language)
        if not normalized_target or normalized_target == normalized_source:
            continue

        texts = [
            _stringify_field_value(field, source_fields.get(field))
            for field in TRANSLATABLE_FIELDS
        ]
        response = requests.post(
            api_url,
            data={
                "auth_key": Config.DEEPL_API_KEY,
                "source_lang": _deepl_language_code(normalized_source),
                "target_lang": _deepl_language_code(normalized_target),
                "text": texts,
                "tag_handling": "html",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json() or {}
        translated_values = payload.get("translations") or []
        if len(translated_values) != len(TRANSLATABLE_FIELDS):
            raise RuntimeError("DeepL returned an unexpected translation payload")

        entry = {}
        for field, translated in zip(TRANSLATABLE_FIELDS, translated_values):
            entry[field] = _parse_translated_field_value(
                field, translated.get("text", "")
            )

        entry["_meta"] = {
            "provider": "deepl",
            "source_language": normalized_source,
            "target_language": normalized_target,
            "auto_generated": True,
        }
        suggestions[normalized_target] = entry

    return suggestions
