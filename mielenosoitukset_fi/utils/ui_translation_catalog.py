from __future__ import annotations

import errno
import logging
import os
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Iterable
from urllib.parse import unquote_plus

from babel.messages import mofile, pofile
from flask import current_app
from mielenosoitukset_fi.utils.logger import logger


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
    """
    Persist a gettext catalog (.po and .mo files) to disk.

    ⚠️ Environment note
    -------------------
    In some development or CI environments, the application filesystem may be
    mounted as read-only. In those cases, this function may fail with
    OSError: [Errno 30] Read-only file system.

    The UI translation system is designed so that filesystem writes are not
    strictly required for correctness in all environments:
    - Approved translations are stored in the database (proposal system)
    - GitHub sync is responsible for persisting translations to source control
    - Local .po/.mo writes are primarily for development convenience

    In read-only environments, failures should be treated as non-fatal and
    logged, not as application errors.
    """
    po_path = _po_path(locale, root=root)
    mo_path = _mo_path(locale, root=root)

    try:
        po_path.parent.mkdir(parents=True, exist_ok=True)
        mo_path.parent.mkdir(parents=True, exist_ok=True)

        # --- atomic write PO ---
        with NamedTemporaryFile(
            mode="wb",
            delete=False,
            dir=str(po_path.parent),
        ) as tmp_po:
            pofile.write_po(tmp_po, catalog, width=120)
            tmp_po_path = Path(tmp_po.name)

        os.replace(tmp_po_path, po_path)

        # --- atomic write MO ---
        with NamedTemporaryFile(
            mode="wb",
            delete=False,
            dir=str(mo_path.parent),
        ) as tmp_mo:
            mofile.write_mo(tmp_mo, catalog, use_fuzzy=False)
            tmp_mo_path = Path(tmp_mo.name)

        os.replace(tmp_mo_path, mo_path)

    except OSError as exc:
        # Dev containers / CI / read-only mounts
        if exc.errno == errno.EROFS:
            logger.warning(
                "Skipping catalog write (read-only filesystem): %s",
                po_path,
            )
            return

        logger.exception("Failed to save catalog (OS error)")
        raise

    except Exception:
        logger.exception("Failed to save catalog")
        raise

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
