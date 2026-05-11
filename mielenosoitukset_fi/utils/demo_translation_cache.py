from __future__ import annotations

import hashlib
import json
from datetime import datetime, date
from typing import Iterable

from bson import ObjectId

from mielenosoitukset_fi.utils.database import get_database_manager
from mielenosoitukset_fi.utils.demo_translation_suggestions import (
    build_deepl_translation_suggestions,
)


translation_suggestions_collection = None


def _get_translation_suggestions_collection():
    global translation_suggestions_collection
    if translation_suggestions_collection is not None:
        return translation_suggestions_collection

    mongo = get_database_manager()
    translation_suggestions_collection = mongo["demo_translation_suggestions"]

    try:
        translation_suggestions_collection.create_index(
            [("demo_id", 1), ("provider", 1), ("source_hash", 1)],
            background=True,
        )
    except Exception:
        pass

    return translation_suggestions_collection


def _demo_source_payload(demo):
    if hasattr(demo, "to_dict"):
        demo = demo.to_dict(json=False)

    if not isinstance(demo, dict):
        raise TypeError("demo must be a Demonstration instance or a dict")

    return {
        "title": demo.get("title", ""),
        "description": demo.get("description", ""),
        "tags": demo.get("tags") or [],
    }


def _normalize_target_languages(target_languages: Iterable[str], source_language: str):
    normalized_source = (source_language or "fi").strip().lower()
    normalized = []
    for language in target_languages:
        language_code = (language or "").strip().lower()
        if not language_code or language_code == normalized_source:
            continue
        if language_code not in normalized:
            normalized.append(language_code)
    return normalized


def _source_hash(source_payload: dict, source_language: str, target_languages: Iterable[str]) -> str:
    encoded = json.dumps(
        {
            "source_language": (source_language or "fi").strip().lower(),
            "target_languages": list(target_languages),
            "source_payload": source_payload,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def demo_is_translation_candidate(demo, *, today: date | None = None, include_past: bool = False) -> bool:
    if hasattr(demo, "to_dict"):
        demo = demo.to_dict(json=False)

    if not isinstance(demo, dict):
        raise TypeError("demo must be a Demonstration instance or a dict")

    if include_past:
        return True

    demo_date = demo.get("date")
    if not demo_date:
        return True

    reference_day = today or datetime.utcnow().date()
    try:
        parsed = datetime.strptime(str(demo_date), "%Y-%m-%d").date()
    except ValueError:
        return True

    return parsed >= reference_day


def get_cached_deepl_suggestion_for_demo(demo, target_language: str):
    if hasattr(demo, "to_dict"):
        demo_dict = demo.to_dict(json=False)
    else:
        demo_dict = dict(demo)

    source_language = (demo_dict.get("default_language") or "fi").strip().lower()
    normalized_targets = _normalize_target_languages([target_language], source_language)
    if not normalized_targets:
        return None

    source_payload = _demo_source_payload(demo_dict)
    payload_hash = _source_hash(source_payload, source_language, normalized_targets)
    demo_id = demo_dict.get("_id")
    demo_id_str = str(demo_id) if demo_id is not None else None

    doc = _get_translation_suggestions_collection().find_one(
        {
            "demo_id": demo_id_str,
            "provider": "deepl",
            "source_hash": payload_hash,
        }
    )
    if not doc:
        return None

    return {
        "cached": True,
        "provider": "deepl",
        "source_hash": payload_hash,
        "suggestion": (doc.get("suggestions") or {}).get(normalized_targets[0]),
    }


def get_or_create_deepl_suggestions_for_demo(
    demo,
    target_languages: Iterable[str],
    *,
    force_refresh: bool = False,
    include_past: bool = False,
):
    if hasattr(demo, "to_dict"):
        demo_dict = demo.to_dict(json=False)
    else:
        demo_dict = dict(demo)

    if not demo_is_translation_candidate(demo_dict, include_past=include_past):
        return {
            "cached": False,
            "provider": "deepl",
            "skipped": True,
            "reason": "past_demo",
            "suggestions": {},
        }

    source_language = (demo_dict.get("default_language") or "fi").strip().lower()
    normalized_targets = _normalize_target_languages(target_languages, source_language)
    source_payload = _demo_source_payload(demo_dict)
    payload_hash = _source_hash(source_payload, source_language, normalized_targets)
    demo_id = demo_dict.get("_id")
    demo_id_str = str(demo_id) if demo_id is not None else None

    if not force_refresh:
        existing = _get_translation_suggestions_collection().find_one(
            {
                "demo_id": demo_id_str,
                "provider": "deepl",
                "source_hash": payload_hash,
            }
        )
        if existing:
            return {
                "cached": True,
                "provider": "deepl",
                "source_hash": payload_hash,
                "suggestions": existing.get("suggestions") or {},
            }

    suggestions = build_deepl_translation_suggestions(
        source_payload,
        source_language=source_language,
        target_languages=normalized_targets,
    )

    now = datetime.utcnow()
    _get_translation_suggestions_collection().update_one(
        {
            "demo_id": demo_id_str,
            "provider": "deepl",
            "source_hash": payload_hash,
        },
        {
            "$set": {
                "demo_id": demo_id_str,
                "demo_object_id": ObjectId(demo_id) if isinstance(demo_id, str) and ObjectId.is_valid(demo_id) else demo_id,
                "provider": "deepl",
                "source_language": source_language,
                "target_languages": normalized_targets,
                "source_hash": payload_hash,
                "source_payload": source_payload,
                "suggestions": suggestions,
                "updated_at": now,
            },
            "$setOnInsert": {
                "created_at": now,
            },
        },
        upsert=True,
    )

    return {
        "cached": False,
        "provider": "deepl",
        "source_hash": payload_hash,
        "suggestions": suggestions,
    }
