"""Tests for the CI release artifact downloader used by the deploy."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import stat
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "deploy" / "release_artifacts.py"
SHA = "a" * 40
REPOSITORY = "example/mielenosoitukset"
API = b"go-api-binary"
APP = b"react-host-bundle"


@pytest.fixture(scope="module")
def artifacts():
    spec = importlib.util.spec_from_file_location("release_artifacts", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _manifest(artifacts, *, commit=SHA, api=API, app=APP, omit=None):
    assets = {
        "api": {"sha256": hashlib.sha256(api).hexdigest(), "size": len(api)},
        "app.tar.gz": {"sha256": hashlib.sha256(app).hexdigest(), "size": len(app)},
    }
    for name in omit or ():
        assets.pop(name)
    return artifacts.json.dumps(
        {"schema": 1, "commit": commit, "tree": "b" * 40, "assets": assets}
    ).encode()


def _fetch_factory(artifacts, manifest, blobs, *, fail_first=0):
    calls = []

    def fetch(url, *, timeout, limit):
        calls.append(url)
        if len(calls) <= fail_first:
            raise artifacts.ArtifactError("HTTP 404")
        name = url.rsplit("/", 1)[-1]
        if name == "release.json":
            return manifest
        if name in blobs:
            return blobs[name]
        raise artifacts.ArtifactError("HTTP 404")

    return fetch, calls


def _download(artifacts, output, *, manifest=None, blobs=None, fetch=None, **kwargs):
    if manifest is None:
        manifest = _manifest(artifacts)
    if blobs is None:
        blobs = {"api": API, "app.tar.gz": APP}
    if fetch is None:
        fetch, _ = _fetch_factory(artifacts, manifest, blobs)
    return artifacts.download_release(
        REPOSITORY,
        SHA,
        output,
        fetch=fetch,
        sleep=lambda _seconds: None,
        attempts=kwargs.pop("attempts", 1),
        **kwargs,
    )


def test_downloads_and_verifies_both_assets(artifacts, tmp_path):
    fetch, calls = _fetch_factory(artifacts, _manifest(artifacts), {"api": API, "app.tar.gz": APP})
    output = tmp_path / "assets"

    written = _download(artifacts, output, fetch=fetch)

    assert written["api"].read_bytes() == API
    assert written["app.tar.gz"].read_bytes() == APP
    assert stat.S_IMODE(written["api"].stat().st_mode) == 0o600
    assert calls == [
        f"https://github.com/{REPOSITORY}/releases/download/release-{SHA}/release.json",
        f"https://github.com/{REPOSITORY}/releases/download/release-{SHA}/api",
        f"https://github.com/{REPOSITORY}/releases/download/release-{SHA}/app.tar.gz",
    ]


def test_rejects_an_asset_that_does_not_match_the_manifest(artifacts, tmp_path):
    # Same length as the recorded artifact, so only the digest can reject it.
    tampered = b"x" * len(API)
    fetch, _ = _fetch_factory(
        artifacts, _manifest(artifacts), {"api": tampered, "app.tar.gz": APP}
    )

    with pytest.raises(artifacts.ArtifactError, match="sha256"):
        _download(artifacts, tmp_path / "assets", fetch=fetch)

    assert not (tmp_path / "assets" / "api").exists()


def test_rejects_a_manifest_for_another_commit(artifacts, tmp_path):
    fetch, _ = _fetch_factory(
        artifacts,
        _manifest(artifacts, commit="c" * 40),
        {"api": API, "app.tar.gz": APP},
    )

    with pytest.raises(artifacts.ArtifactError, match="different commit"):
        _download(artifacts, tmp_path / "assets", fetch=fetch)


def test_rejects_a_release_without_the_requested_asset(artifacts, tmp_path):
    fetch, _ = _fetch_factory(artifacts, _manifest(artifacts, omit=["app.tar.gz"]), {"api": API})

    with pytest.raises(artifacts.ArtifactError, match="missing"):
        _download(artifacts, tmp_path / "assets", fetch=fetch)


def test_retries_a_release_that_is_not_published_yet(artifacts, tmp_path):
    fetch, calls = _fetch_factory(
        artifacts,
        _manifest(artifacts),
        {"api": API, "app.tar.gz": APP},
        fail_first=2,
    )

    written = _download(artifacts, tmp_path / "assets", fetch=fetch, attempts=3)

    assert len(calls) == 5
    assert written["api"].read_bytes() == API


def test_rejects_unsafe_asset_names(artifacts, tmp_path):
    with pytest.raises(artifacts.ArtifactError, match="unsafe"):
        _download(artifacts, tmp_path / "assets", assets=("../api",))


def test_rejects_invalid_repository_and_tag(artifacts):
    with pytest.raises(artifacts.ArtifactError):
        artifacts.release_base("no-slash", "release-" + SHA)
    with pytest.raises(artifacts.ArtifactError):
        artifacts.release_base(REPOSITORY, "release/../escape")


def test_cli_reports_a_bad_sha_without_downloading(artifacts, tmp_path, capsys):
    status = artifacts.main(
        ["--repository", REPOSITORY, "--sha", "not-a-sha", "--output", str(tmp_path)]
    )

    assert status == 1
    assert "40-character" in capsys.readouterr().err


def test_manifest_size_mismatch_is_rejected(artifacts, tmp_path):
    manifest = json.loads(_manifest(artifacts))
    manifest["assets"]["api"]["size"] += 1
    fetch, _ = _fetch_factory(
        artifacts,
        json.dumps(manifest).encode(),
        {"api": API, "app.tar.gz": APP},
    )

    with pytest.raises(artifacts.ArtifactError, match="size"):
        _download(artifacts, tmp_path / "assets", fetch=fetch)
