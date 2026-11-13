#!/usr/bin/env python3
"""Publish one verified SHA release, or reuse its existing immutable artifacts.

All GitHub access goes through the authenticated gh CLI. Existing drafts and
incomplete releases require manual repair; this helper never replaces assets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

FULL_SHA = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
ASSETS = ("api", "app.tar.gz", "release.json")
MAX_ASSET_BYTES = 100 * 1024 * 1024
MAX_MANIFEST_BYTES = 64 * 1024


class PublicationError(RuntimeError):
    """Publication cannot safely continue."""


def gh(*arguments: str, allow_missing: bool = False) -> bytes | None:
    try:
        result = subprocess.run(
            ["gh", *arguments], capture_output=True, check=False, timeout=300
        )
    except (OSError, subprocess.TimeoutExpired):
        raise PublicationError("GitHub CLI could not complete the request") from None
    if result.returncode:
        # gh includes the HTTP status in parentheses; generic failures are never
        # interpreted as an absent release (including authentication failures).
        if allow_missing and re.search(rb"\(HTTP 404\)(?:\r?\n|$)", result.stderr):
            return None
        raise PublicationError("GitHub CLI request failed; response withheld")
    return result.stdout


def json_request(*arguments: str, allow_missing: bool = False):
    raw = gh("api", "--hostname", "github.com", *arguments, allow_missing=allow_missing)
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise PublicationError("GitHub returned invalid JSON") from None
    if not isinstance(value, dict):
        raise PublicationError("GitHub returned unexpected metadata")
    return value


def api(repository: str, endpoint: str, *, allow_missing: bool = False):
    return json_request(f"repos/{repository}/{endpoint}", allow_missing=allow_missing)


def find_release(repository: str, sha: str):
    tag = f"release-{sha}"
    release = api(repository, f"releases/tags/{tag}", allow_missing=True)
    if release is not None:
        return release
    # REST tag lookup only finds published releases. An explicit REST 404 must
    # also be checked for an authenticated draft before allowing a new build.
    owner, name = repository.split("/")
    result = json_request(
        "graphql", "--raw-field",
        "query=query($owner:String!,$name:String!,$tag:String!){repository(owner:$owner,name:$name){release(tagName:$tag){databaseId}}}",
        "--raw-field", f"owner={owner}", "--raw-field", f"name={name}",
        "--raw-field", f"tag={tag}",
    )
    try:
        if result.get("errors"):
            raise PublicationError("GitHub draft lookup failed")
        candidate = result["data"]["repository"]["release"]
        if candidate is None:
            return None
        release_id = candidate["databaseId"]
        if type(release_id) is not int:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise PublicationError("GitHub returned invalid draft metadata") from None
    return api(repository, f"releases/{release_id}")


def verify_files(directory: Path, sha: str, tree: str) -> None:
    paths = {name: directory / name for name in ASSETS}
    for name, path in paths.items():
        limit = MAX_MANIFEST_BYTES if name == "release.json" else MAX_ASSET_BYTES
        if not path.is_file() or path.is_symlink() or path.stat().st_size > limit:
            raise PublicationError(f"missing or invalid asset: {name}")
    try:
        manifest = json.loads(paths["release.json"].read_bytes())
    except (ValueError, UnicodeDecodeError):
        raise PublicationError("release.json is not valid JSON") from None
    if not isinstance(manifest, dict) or type(manifest.get("schema")) is not int or manifest["schema"] != 1:
        raise PublicationError("release.json has an unexpected schema")
    if manifest.get("commit") != sha or manifest.get("tree") != tree:
        raise PublicationError("release.json commit or tree does not match")
    entries = manifest.get("assets")
    if not isinstance(entries, dict) or set(entries) != set(ASSETS[:-1]):
        raise PublicationError("release.json must describe exactly api and app.tar.gz")
    for name in ASSETS[:-1]:
        entry = entries[name]
        if not isinstance(entry, dict):
            raise PublicationError(f"invalid manifest entry: {name}")
        digest, size = entry.get("sha256"), entry.get("size")
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise PublicationError(f"invalid sha256: {name}")
        if type(size) is not int or size < 0 or size != paths[name].stat().st_size:
            raise PublicationError(f"asset size does not match: {name}")
        if hashlib.sha256(paths[name].read_bytes()).hexdigest() != digest:
            raise PublicationError(f"asset sha256 does not match: {name}")


def verify_tag(repository: str, sha: str, *, allow_missing: bool = False) -> None:
    ref = api(repository, f"git/ref/tags/release-{sha}", allow_missing=allow_missing)
    if ref is None:
        return
    target = ref.get("object")
    # Annotated tags are deliberately rejected instead of trusting an unpeeled
    # object ID. The workflow creates lightweight tags for these releases.
    if not isinstance(target, dict) or target.get("type") != "commit" or target.get("sha") != sha:
        raise PublicationError("release tag does not point directly to the expected commit")


def verify_release(repository: str, sha: str, tree: str, release: dict, *, own_draft: bool = False) -> None:
    if not isinstance(release, dict) or release.get("tag_name") != f"release-{sha}" or type(release.get("id")) is not int:
        raise PublicationError("release metadata does not match the requested tag")
    if type(release.get("draft")) is not bool or release["draft"] != own_draft:
        raise PublicationError("existing draft release requires manual repair")
    if release.get("prerelease") is not False:
        raise PublicationError("unexpected prerelease requires manual repair")
    if own_draft and release.get("target_commitish") != sha:
        raise PublicationError("draft release targets a different commit")
    verify_tag(repository, sha, allow_missing=own_draft)
    assets = release.get("assets")
    if not isinstance(assets, list) or len(assets) != len(ASSETS):
        raise PublicationError("incomplete release assets require manual repair")
    by_name = {}
    for asset in assets:
        if not isinstance(asset, dict) or asset.get("name") not in ASSETS or asset["name"] in by_name:
            raise PublicationError("unexpected or duplicate release asset")
        name = asset["name"]
        limit = MAX_MANIFEST_BYTES if name == "release.json" else MAX_ASSET_BYTES
        if type(asset.get("id")) is not int or type(asset.get("size")) is not int or not 0 <= asset["size"] <= limit:
            raise PublicationError(f"invalid GitHub asset metadata: {name}")
        if asset.get("state") != "uploaded":
            raise PublicationError(f"unfinished GitHub asset: {name}")
        by_name[name] = asset
    with tempfile.TemporaryDirectory(prefix="moso-release-verify-") as temporary:
        directory = Path(temporary)
        for name in ASSETS:
            asset = by_name[name]
            raw = gh(
                "api", "--hostname", "github.com",
                f"repos/{repository}/releases/assets/{asset['id']}",
                "--header", "Accept: application/octet-stream",
            )
            if raw is None or len(raw) != asset["size"]:
                raise PublicationError(f"downloaded asset size does not match: {name}")
            digest = asset.get("digest")
            if digest is not None and digest != "sha256:" + hashlib.sha256(raw).hexdigest():
                raise PublicationError(f"GitHub asset digest does not match: {name}")
            (directory / name).write_bytes(raw)
        verify_files(directory, sha, tree)


def reusable_output(reusable: bool) -> None:
    value = "true" if reusable else "false"
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with Path(output).open("a", encoding="utf-8") as handle:
            handle.write(f"reusable={value}\n")
    print(f"reusable={value}")


def publish(repository: str, sha: str, tree: str, directory: Path | None) -> bool:
    if not REPOSITORY.fullmatch(repository) or any(part in {".", ".."} for part in repository.split("/")):
        raise PublicationError("invalid repository; expected owner/repo")
    if not FULL_SHA.fullmatch(sha) or not FULL_SHA.fullmatch(tree):
        raise PublicationError("commit and tree must be full lowercase 40-character SHAs")
    if directory is not None:
        verify_files(directory, sha, tree)
    tag = f"release-{sha}"
    release = find_release(repository, sha)
    if release is not None:
        verify_release(repository, sha, tree, release)
        return True
    if directory is None:
        return False
    # Check orphaned tags before creating anything. Drafts do not necessarily
    # create their tag until publication, so an absent tag here is expected.
    verify_tag(repository, sha, allow_missing=True)
    try:
        gh(
            "release", "create", tag, "--repo", f"github.com/{repository}",
            "--target", sha, "--draft", "--latest=false", "--title", tag,
            "--notes", f"Verified production artifacts for {sha}.",
        )
        gh(
            "release", "upload", tag, "--repo", f"github.com/{repository}",
            *(str((directory / name).resolve()) for name in ASSETS),
        )
        draft = find_release(repository, sha)
        verify_release(repository, sha, tree, draft, own_draft=True)
        gh(
            "api", "--hostname", "github.com", f"repos/{repository}/releases/{draft['id']}",
            "--method", "PATCH", "--field", "draft=false", "--raw-field", "make_latest=false",
        )
        verify_release(repository, sha, tree, api(repository, f"releases/tags/{tag}"))
    except (PublicationError, OSError) as error:
        message = str(error) if isinstance(error, PublicationError) else "local artifact access failed"
        raise PublicationError(f"{message}; repair needed for {tag}; no assets were replaced") from None
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--tree", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--publish", action="store_true")
    parser.add_argument("--directory", type=Path)
    arguments = parser.parse_args(argv)
    if arguments.publish != (arguments.directory is not None):
        parser.error("--directory is required only with --publish")
    try:
        reused = publish(arguments.repository, arguments.sha, arguments.tree, arguments.directory)
        reusable_output(reused)
        if arguments.publish:
            print("Existing release verified and reused." if reused else "Release published and verified.")
        elif not reused:
            print("Release is absent; build required.")
    except (PublicationError, OSError) as error:
        message = str(error) if isinstance(error, PublicationError) else "local artifact or output file access failed"
        print(f"release publication failed: {message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
