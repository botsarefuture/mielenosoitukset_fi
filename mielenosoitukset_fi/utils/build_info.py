"""Resolve immutable build metadata for one application worker."""

from __future__ import annotations

import os
from pathlib import Path
import re


_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
_DEFAULT_BUILD_FILE = Path(__file__).resolve().parents[2] / ".deploy-build-sha"


def resolve_build_sha() -> str:
    """Return the build SHA captured when the worker creates its Flask app.

    Production deploys atomically update ``.deploy-build-sha`` before asking
    Gunicorn to replace its workers. Existing workers retain their old value,
    which lets health verification distinguish them from replacement workers.
    Container builds can provide the same value through the environment.
    """
    configured = os.environ.get("MIELENOSOITUKSET_BUILD_SHA", "").strip().lower()
    if configured:
        return configured if _FULL_SHA.fullmatch(configured) else "unknown"

    build_file = Path(
        os.environ.get("MIELENOSOITUKSET_BUILD_SHA_FILE", _DEFAULT_BUILD_FILE)
    )
    try:
        deployed = build_file.read_text(encoding="utf-8").strip().lower()
    except OSError:
        return "unknown"
    return deployed if _FULL_SHA.fullmatch(deployed) else "unknown"
