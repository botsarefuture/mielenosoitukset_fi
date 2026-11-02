#!/usr/bin/env python3
"""Download and verify the CI-built public release artifacts for one commit.

The production deploy is triggered with a commit SHA. The matching GitHub
release carries the exact React host bundle and Go API binary that CI built for
that commit, so the server never compiles anything and never depends on a
developer workstation.

Trust model: the assets come from the same GitHub repository the deploy already
fetches from, and every asset is checked against the SHA-256 in ``release.json``
while ``release.json`` must name the requested commit. A missing, extra, renamed
or modified asset aborts the deploy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

SCHEMA = 1
DEFAULT_ASSETS = ("api", "app.tar.gz")
MAX_ASSET_BYTES = 100 * 1024 * 1024
MAX_MANIFEST_BYTES = 64 * 1024
READ_CHUNK = 64 * 1024
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SAFE_ASSET_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class ArtifactError(RuntimeError):
    """The release metadata or one of its assets is unusable."""


def default_tag(sha: str) -> str:
    return f"release-{sha}"


def release_base(repository: str, tag: str) -> str:
    if not REPOSITORY.fullmatch(repository):
        raise ArtifactError("invalid repository name; expected owner/name")
    if not tag or any(character in tag for character in "\n\r\0/"):
        raise ArtifactError("invalid release tag")
    return (
        f"https://github.com/{repository}/releases/download/"
        f"{quote(tag, safe='')}"
    )


def fetch(url: str, *, timeout: float, limit: int) -> bytes:
    """Read one bounded response body without following untrusted redirects."""
    request = Request(
        url,
        headers={
            "User-Agent": "mielenosoitukset-release/1",
            "Accept": "application/octet-stream",
            "Cache-Control": "no-cache",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise ArtifactError(f"HTTP {status}")
            chunks = []
            total = 0
            while True:
                chunk = response.read(READ_CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if total > limit:
                    raise ArtifactError("response exceeds the allowed size")
                chunks.append(chunk)
    except HTTPError as error:
        raise ArtifactError(f"HTTP {error.code}") from None
    except (URLError, TimeoutError, OSError) as error:
        raise ArtifactError(f"request failed: {error.__class__.__name__}") from None
    return b"".join(chunks)


def parse_manifest(raw: bytes, expected_sha: str) -> dict[str, dict]:
    """Validate the release manifest and return its asset descriptions."""
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ArtifactError("release.json is not valid JSON") from None
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise ArtifactError("release.json has an unexpected schema")
    if manifest.get("commit") != expected_sha:
        raise ArtifactError("release.json names a different commit")
    assets = manifest.get("assets")
    if not isinstance(assets, dict) or not assets:
        raise ArtifactError("release.json lists no assets")
    parsed: dict[str, dict] = {}
    for name, entry in assets.items():
        if not isinstance(name, str) or not SAFE_ASSET_NAME.fullmatch(name):
            raise ArtifactError("release.json contains an unsafe asset name")
        if not isinstance(entry, dict):
            raise ArtifactError(f"release.json entry for {name} is invalid")
        digest = entry.get("sha256")
        size = entry.get("size")
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise ArtifactError(f"release.json has no valid sha256 for {name}")
        if size is not None and (
            not isinstance(size, int) or isinstance(size, bool) or size < 0
        ):
            raise ArtifactError(f"release.json has no valid size for {name}")
        parsed[name] = {"sha256": digest, "size": size}
    return parsed


def _fetch_retrying(url, *, timeout, limit, fetch, sleep, attempts, delay):
    last = None
    for attempt in range(1, attempts + 1):
        try:
            return fetch(url, timeout=timeout, limit=limit)
        except ArtifactError as error:
            last = error
            if attempt < attempts:
                sleep(delay)
    raise ArtifactError(f"could not read {url.rsplit('/', 1)[-1]}: {last}")


def _write_atomic(destination: Path, data: bytes) -> None:
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="wb", dir=destination.parent, prefix=".asset-", delete=False
    )
    temporary = Path(handle.name)
    try:
        with handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def download_release(
    repository: str,
    sha: str,
    output: Path,
    *,
    assets: tuple[str, ...] = DEFAULT_ASSETS,
    tag: str | None = None,
    fetch=fetch,
    sleep=time.sleep,
    attempts: int = 20,
    delay: float = 2.0,
    timeout: float = 60.0,
) -> dict[str, Path]:
    """Download and verify the requested assets into ``output``."""
    if not FULL_SHA.fullmatch(sha):
        raise ArtifactError("expected a full 40-character commit SHA")
    if not assets:
        raise ArtifactError("at least one asset is required")
    for name in assets:
        if not SAFE_ASSET_NAME.fullmatch(name):
            raise ArtifactError(f"unsafe asset name: {name}")
    base = release_base(repository, tag or default_tag(sha))
    manifest_raw = _fetch_retrying(
        f"{base}/release.json",
        timeout=timeout,
        limit=MAX_MANIFEST_BYTES,
        fetch=fetch,
        sleep=sleep,
        attempts=attempts,
        delay=delay,
    )
    described = parse_manifest(manifest_raw, sha)
    missing = [name for name in assets if name not in described]
    if missing:
        raise ArtifactError("release is missing: " + ", ".join(sorted(missing)))

    output = Path(output)
    written: dict[str, Path] = {}
    for name in assets:
        entry = described[name]
        data = _fetch_retrying(
            f"{base}/{quote(name, safe='')}",
            timeout=timeout,
            limit=MAX_ASSET_BYTES,
            fetch=fetch,
            sleep=sleep,
            attempts=attempts,
            delay=delay,
        )
        if entry["size"] is not None and len(data) != entry["size"]:
            raise ArtifactError(f"{name} size does not match release.json")
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ArtifactError(f"{name} does not match its recorded sha256")
        destination = output / name
        _write_atomic(destination, data)
        written[name] = destination
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, help="GitHub owner/name")
    parser.add_argument("--sha", required=True, help="40-character commit SHA")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--tag", help="release tag (default: release-<sha>)")
    parser.add_argument(
        "--asset", action="append", dest="assets", metavar="NAME",
        help="asset to download; repeat for more (default: api, app.tar.gz)",
    )
    parser.add_argument("--attempts", type=int, default=20)
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--timeout", type=float, default=60.0)
    arguments = parser.parse_args(argv)
    chosen = tuple(arguments.assets or DEFAULT_ASSETS)
    try:
        written = download_release(
            arguments.repository,
            arguments.sha,
            arguments.output,
            assets=chosen,
            tag=arguments.tag,
            attempts=arguments.attempts,
            delay=arguments.delay,
            timeout=arguments.timeout,
        )
    except ArtifactError as error:
        print(f"release_artifacts: {error}", file=sys.stderr)
        return 1
    for name, path in written.items():
        print(f"release_artifacts: verified {name} -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
