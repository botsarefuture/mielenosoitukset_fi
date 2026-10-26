"""Resolve page-specific Vite entries without adding a JavaScript server runtime."""

import json
from pathlib import Path, PurePosixPath

from flask import current_app, url_for


def frontend_assets(entry):
    """Return an entry's script and dependency CSS in the manifest's import order."""
    build_dir = Path(current_app.static_folder) / "frontend"
    # Read on demand so `npm run dev` rebuilds work without restarting Flask.
    manifest = json.loads((build_dir / "manifest.json").read_text(encoding="utf-8"))
    styles = []
    visited = set()

    def asset_url(filename):
        path = PurePosixPath(filename)
        if path.is_absolute() or ".." in path.parts or not (build_dir / filename).is_file():
            raise ValueError(f"Invalid or missing frontend build asset: {filename}")
        return url_for("static", filename=f"frontend/{filename}")

    def collect_styles(key):
        if key in visited:
            return
        visited.add(key)
        chunk = manifest[key]
        for dependency in chunk.get("imports", []):
            collect_styles(dependency)
        for filename in chunk.get("css", []):
            if filename not in styles:
                styles.append(filename)

    collect_styles(entry)
    return {
        "script": asset_url(manifest[entry]["file"]),
        "styles": [asset_url(filename) for filename in styles],
    }
