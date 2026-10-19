#!/usr/bin/env python3
"""Install pinned browser dependencies locally; keep sandbox CSP self-only."""
import hashlib
from pathlib import Path
import socket
from urllib.request import urlopen

ASSETS = {
    "bootstrap-5.3.3.bundle.min.js": (
        "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js",
        "0833b2e9c3a26c258476c46266e6877fc75218625162e0460be9a3a098a61c6c"),
    "jquery-3.7.0.min.js": (
        "https://code.jquery.com/jquery-3.7.0.min.js",
        "d8f9afbf492e4c139e9d2bcb9ba6ef7c14921eb509fb703bc7a3f911b774eff8"),
}


def install(root):
    root.mkdir(parents=True, exist_ok=True)
    for name, (url, expected) in ASSETS.items():
        target = root / name
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
            continue
        with urlopen(url, timeout=30) as response:
            data = response.read(2 * 1024 * 1024)
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("Browser dependency checksum mismatch: " + name)
        pending = root / (name + ".tmp")
        pending.write_bytes(data)
        pending.chmod(0o644)
        pending.replace(target)


if __name__ == "__main__":
    if socket.gethostname() != "mielenosoitukset-pentest":
        raise RuntimeError("Run on the sandbox only")
    install(Path("/srv/mielenosoitukset-dr/app/mielenosoitukset_fi/static/dr-vendor"))
