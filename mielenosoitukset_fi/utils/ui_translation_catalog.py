from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote_plus

from babel.messages import mofile, pofile
from flask import current_app


@dataclass(frozen=True)
class CatalogEntrySnapshot:
    locale: str
    msgid: str
    msgstr: str
    flags: tuple[str, ...]
    locations: tuple[str, ...]


def _translations_root(root: str | Path | None = None) -> Path:
    if root:
        return Path(root)
    configured = current_app.config.get("TRANSLATIONS_DIR")
    if configured:
        return Path(configured)
    return Path(current_app.root_path) / "translations"


def _po_path(locale: str, root: str | Path | None = None) -> Path:
    return _translations_root(root) / locale / "LC_MESSAGES" / "messages.po"


def _mo_path(locale: str, root: str | Path | None = None) -> Path:
    return _translations_root(root) / locale / "LC_MESSAGES" / "messages.mo"


def supported_ui_translation_locales() -> list[str]:
    locales = current_app.config.get("BABEL_SUPPORTED_LOCALES", [])
    default_locale = current_app.config.get("BABEL_DEFAULT_LOCALE", "fi")
    return [locale for locale in locales if locale != default_locale]


def load_catalog(locale: str, root: str | Path | None = None):
    po_path = _po_path(locale, root=root)
    if not po_path.exists():
        raise FileNotFoundError(f"Missing gettext catalog: {po_path}")

    with po_path.open("r", encoding="utf-8") as handle:
        return pofile.read_po(handle, locale=locale)


def save_catalog(locale: str, catalog, root: str | Path | None = None) -> None:
    po_path = _po_path(locale, root=root)
    mo_path = _mo_path(locale, root=root)
    po_path.parent.mkdir(parents=True, exist_ok=True)
    mo_path.parent.mkdir(parents=True, exist_ok=True)

    with po_path.open("wb") as handle:
        pofile.write_po(handle, catalog, width=120)

    with mo_path.open("wb") as handle:
        mofile.write_mo(handle, catalog, use_fuzzy=False)


def _normalize_locations(locations: Iterable[tuple[str, int]] | None) -> tuple[str, ...]:
    result = []
    for filename, lineno in locations or []:
        if lineno:
            result.append(f"{filename}:{lineno}")
        else:
            result.append(str(filename))
    return tuple(result)


def iter_catalog_entries(locale: str, root: str | Path | None = None):
    catalog = load_catalog(locale, root=root)
    for message in catalog:
        if not message.id or isinstance(message.id, tuple):
            continue
        yield CatalogEntrySnapshot(
            locale=locale,
            msgid=str(message.id),
            msgstr=str(message.string or ""),
            flags=tuple(sorted(message.flags or [])),
            locations=_normalize_locations(message.locations),
        )


def get_catalog_entry(locale: str, msgid: str, root: str | Path | None = None):
    catalog = load_catalog(locale, root=root)
    message = catalog.get(msgid)
    if message is None and msgid:
        normalized_msgid = " ".join(unquote_plus(str(msgid)).split())
        for candidate in catalog:
            if not candidate.id or isinstance(candidate.id, tuple):
                continue
            if " ".join(str(candidate.id).split()) == normalized_msgid:
                message = candidate
                break
    if message is None:
        return None
    return CatalogEntrySnapshot(
        locale=locale,
        msgid=str(message.id),
        msgstr=str(message.string or ""),
        flags=tuple(sorted(message.flags or [])),
        locations=_normalize_locations(message.locations),
    )


def update_catalog_entry(locale: str, msgid: str, translated_text: str, root: str | Path | None = None):
    catalog = load_catalog(locale, root=root)
    message = catalog.get(msgid)
    if message is None:
        raise KeyError(msgid)

    message.string = translated_text
    if "fuzzy" in (message.flags or set()):
        message.flags.discard("fuzzy")
    save_catalog(locale, catalog, root=root)


def entry_state(snapshot: CatalogEntrySnapshot) -> str:
    if "fuzzy" in snapshot.flags:
        return "fuzzy"
    if not snapshot.msgstr.strip():
        return "untranslated"
    return "translated"


def proposal_key(locale: str, msgid: str) -> str:
    return sha256(f"{locale}\0{msgid}".encode("utf-8")).hexdigest()
