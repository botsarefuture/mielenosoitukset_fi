#!/usr/bin/env python3
"""Install pinned browser dependencies locally; keep sandbox CSP self-only."""
import hashlib
import io
from pathlib import Path
import socket
import argparse
import tarfile
from urllib.request import urlopen

ASSETS = {
    "bootstrap-5.3.3.bundle.min.js": (
        "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js",
        "0833b2e9c3a26c258476c46266e6877fc75218625162e0460be9a3a098a61c6c"),
    "jquery-3.7.0.min.js": (
        "https://code.jquery.com/jquery-3.7.0.min.js",
        "d8f9afbf492e4c139e9d2bcb9ba6ef7c14921eb509fb703bc7a3f911b774eff8"),
    'jquery-3.6.0.min.js': ('https://code.jquery.com/jquery-3.6.0.min.js', 'ff1523fb7389539c84c65aba19260648793bb4f5e29329d2ee8804bc37a3fe6e'),
    'quill-1.3.6.min.js': ('https://cdn.quilljs.com/1.3.6/quill.min.js', 'de86018869b5e845bdc101fc1b55611a1e375e08af6cee4a681d7446103da611'),
    'quill-1.3.6.snow.css': ('https://cdn.quilljs.com/1.3.6/quill.snow.css', '892e299431955e9ae388ae257f72024ee76af2d52a7a97a868f70fbe50f16144'),
    'quill-1.3.6.bubble.css': ('https://cdn.quilljs.com/1.3.6/quill.bubble.css', '48b1b42379c43ddbbf6ca013334f983068a10a62f6d223432a166872ec0ec0e9'),
    'quill-1.3.6.core.css': ('https://cdn.quilljs.com/1.3.6/quill.core.css', 'b6235e6b05b8c5d649479fe9f6113622410930ced252e5fceeea53caa3eab7d9'),
    'flatpickr-4.6.13.min.js': ('https://cdn.jsdelivr.net/npm/flatpickr@4.6.13/dist/flatpickr.min.js', '1eeab1cb779471a0b0aaa93dd91c2eb1aa537d696f01ab05ea9dabc55e8525a1'),
    'flatpickr-4.6.13.min.css': ('https://cdn.jsdelivr.net/npm/flatpickr@4.6.13/dist/flatpickr.min.css', '1b34a42552c96f10e4dfaaa4a367276b03868aacff63c1ac42ffe331352bc754'),
    'socket.io-4.7.2.min.js': ('https://cdn.socket.io/4.7.2/socket.io.min.js', '83df4abc7eec941f1d29ae254e80bac0bb82d398fbe2e8ee4ea2a7efc8e704f1'),
    'ckeditor5-43.2.0.css': ('https://cdn.ckeditor.com/ckeditor5/43.2.0/ckeditor5.css', 'a855267748d0c262e1593228098e14c3560ef71fae185dcf12cb8f3459f0420d'),

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


def pack_assets(root, destination):
    pending = destination.with_name(destination.name + '.tmp')
    with tarfile.open(pending, 'w:gz') as archive:
        for name, (_, expected) in sorted(ASSETS.items()):
            path = root / name
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError('Browser dependency checksum mismatch: ' + name)
            member = tarfile.TarInfo(name)
            member.size = len(data)
            member.mode = 0o644
            archive.addfile(member, io.BytesIO(data))
    pending.chmod(0o600)
    pending.replace(destination)


if __name__ == "__main__":
    if socket.gethostname() != "mielenosoitukset-pentest":
        raise RuntimeError("Run on the sandbox only")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack', type=Path)
    args = parser.parse_args()
    root = Path('/srv/mielenosoitukset-dr/app/mielenosoitukset_fi/static/dr-vendor')
    install(root)
    if args.pack:
        pack_assets(root, args.pack)
