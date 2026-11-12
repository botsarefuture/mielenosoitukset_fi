"""Resolve page-specific Vite entries without adding a JavaScript server runtime."""

import json
from pathlib import Path, PurePosixPath

from flask import current_app, url_for


def frontend_assets(entry):
    """Return an entry's script and dependency CSS in the manifest's import order."""
    build_dir = Path(current_app.static_folder) / "frontend"
    # Reuse parsed builds across requests, while reloads still notice watch/release
    # updates. This avoids reading/parsing JSON on every campaign request.
    manifest_path = build_dir / "manifest.json"
    stat = manifest_path.stat()
    signature = (stat.st_mtime_ns, stat.st_size)
    cache = current_app.extensions.setdefault("frontend_manifest_cache", {})
    cached = cache.get(manifest_path)
    if cached is None or cached[0] != signature:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        cache[manifest_path] = (signature, manifest)
    else:
        manifest = cached[1]
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
