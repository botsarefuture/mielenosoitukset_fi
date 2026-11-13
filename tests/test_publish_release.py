"""Immutable release publication checks, with no real GitHub writes."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "deploy" / "publish_release.py"
SHA = "a" * 40
TREE = "b" * 40
REPOSITORY = "example/mielenosoitukset"
TAG = f"release-{SHA}"


@pytest.fixture(scope="module")
def publisher():
    spec = importlib.util.spec_from_file_location("publish_release", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def artifacts(tmp_path):
    blobs = {"api": b"go binary", "app.tar.gz": b"react bundle"}
    manifest = {
        "schema": 1,
        "commit": SHA,
        "tree": TREE,
        "assets": {
            name: {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
            for name, data in blobs.items()
        },
    }
    blobs["release.json"] = json.dumps(manifest).encode()
    for name, data in blobs.items():
        (tmp_path / name).write_bytes(data)
    return tmp_path


class FakeGitHub:
    def __init__(self, directory, *, exists=True):
        self.calls = []
        self.blobs = {name: (directory / name).read_bytes() for name in ("api", "app.tar.gz", "release.json")}
        self.release = {
            "id": 7, "draft": False, "prerelease": False,
            "tag_name": TAG, "target_commitish": SHA, "assets": [],
        } if exists else None
        self.tag = {"object": {"type": "commit", "sha": SHA}} if exists else None
        self.populate_assets()
        self.fail_upload = False
        self.fail_download = False

    def populate_assets(self):
        if self.release is not None:
            self.release["assets"] = [
                {"id": index, "name": name, "size": len(data), "state": "uploaded",
                 "digest": "sha256:" + hashlib.sha256(data).hexdigest()}
                for index, (name, data) in enumerate(self.blobs.items(), start=1)
            ]

    def __call__(self, command, **kwargs):
        assert command[0] == "gh"
        assert kwargs == {"capture_output": True, "check": False, "timeout": 300}
        self.calls.append(command)
        arguments = command[1:]
        result = subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")
        if arguments[:2] == ["release", "create"]:
            assert self.release is None
            assert "--draft" in arguments and "--target" in arguments
            assert arguments[arguments.index("--target") + 1] == SHA
            self.release = {"id": 7, "draft": True, "prerelease": False,
                            "tag_name": TAG, "target_commitish": SHA, "assets": []}
        elif arguments[:2] == ["release", "upload"]:
            assert "--clobber" not in arguments
            assert self.release["draft"]
            if self.fail_upload:
                return subprocess.CompletedProcess(command, 1, b"secret", b"secret")
            paths = [Path(argument) for argument in arguments if argument.startswith("/")]
            assert {path.name for path in paths} == set(self.blobs)
            self.blobs = {path.name: path.read_bytes() for path in paths}
            self.populate_assets()
        else:
            assert arguments[:3] == ["api", "--hostname", "github.com"]
            endpoint = arguments[3]
            assert endpoint == "graphql" or endpoint.startswith(f"repos/{REPOSITORY}/")
            if endpoint == "graphql":
                candidate = {"databaseId": 7} if self.release is not None else None
                value = {"data": {"repository": {"release": candidate}}}
            elif endpoint.endswith(f"releases/tags/{TAG}"):
                value = self.release if self.release is not None and not self.release["draft"] else None
            elif endpoint.endswith(f"git/ref/tags/{TAG}"):
                value = self.tag
            elif "/releases/assets/" in endpoint:
                assert arguments[-2:] == ["--header", "Accept: application/octet-stream"]
                asset_id = int(endpoint.rsplit("/", 1)[1])
                asset = next(asset for asset in self.release["assets"] if asset["id"] == asset_id)
                result.stdout = self.blobs[asset["name"]] + (b"broken" if self.fail_download else b"")
                return result
            elif endpoint.endswith("releases/7"):
                if len(arguments) > 4:
                    assert arguments[4:] == ["--method", "PATCH", "--field", "draft=false", "--raw-field", "make_latest=false"]
                    self.release["draft"] = False
                    self.tag = {"object": {"type": "commit", "sha": SHA}}
                value = self.release
            else:
                raise AssertionError(f"unexpected call: {command}")
            if value is None:
                return subprocess.CompletedProcess(command, 1, b"", b"gh: Not Found (HTTP 404)\n")
            result.stdout = json.dumps(copy.deepcopy(value)).encode()
        return result

    @property
    def mutations(self):
        return [call for call in self.calls if call[1] == "release" or "PATCH" in call]


def install(monkeypatch, publisher, artifacts, *, exists=True):
    fake = FakeGitHub(artifacts, exists=exists)
    monkeypatch.setattr(publisher.subprocess, "run", fake)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    return fake


def cli(publisher, *arguments):
    return publisher.main(["--repository", REPOSITORY, "--sha", SHA, "--tree", TREE, *arguments])


def test_missing_release_is_not_reusable(monkeypatch, publisher, artifacts, tmp_path, capsys):
    fake = install(monkeypatch, publisher, artifacts, exists=False)
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    assert cli(publisher, "--check") == 0
    assert output.read_text() == "reusable=false\n"
    assert "reusable=false" in capsys.readouterr().out
    assert not fake.mutations


@pytest.mark.parametrize("error", [b"unknown release", b"HTTP 403", b"gh: Forbidden (HTTP 403)\n", b"could not resolve host"])
def test_only_explicit_http_404_means_missing(monkeypatch, publisher, error, capsys):
    def fail(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, b"private stdout", error + b" private stderr")
    monkeypatch.setattr(publisher.subprocess, "run", fail)
    assert cli(publisher, "--check") == 1
    captured = capsys.readouterr()
    assert "reusable=false" not in captured.out
    assert "private" not in captured.err
    assert "response withheld" in captured.err


def test_existing_complete_release_reused_without_mutations(monkeypatch, publisher, artifacts, tmp_path):
    fake = install(monkeypatch, publisher, artifacts)
    output = tmp_path / "output"
    output.write_text("prior=keep\n")
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    assert cli(publisher, "--check") == 0
    assert output.read_text() == "prior=keep\nreusable=true\n"
    assert cli(publisher, "--publish", "--directory", str(artifacts)) == 0
    assert not fake.mutations
    assert len([call for call in fake.calls if "/releases/assets/" in " ".join(call)]) == 6


@pytest.mark.parametrize("field,value", [("commit", "c" * 40), ("tree", "c" * 40), ("schema", True)])
def test_existing_manifest_mismatch_fails_closed(monkeypatch, publisher, artifacts, field, value):
    fake = install(monkeypatch, publisher, artifacts)
    manifest = json.loads(fake.blobs["release.json"])
    manifest[field] = value
    fake.blobs["release.json"] = json.dumps(manifest).encode()
    fake.populate_assets()
    assert cli(publisher, "--check") == 1
    assert not fake.mutations


@pytest.mark.parametrize("problem", ["missing", "draft", "duplicate", "uploading", "tag", "annotated", "hash", "size", "digest", "manifest_size"])
def test_invalid_existing_release_never_modified(monkeypatch, publisher, artifacts, problem):
    fake = install(monkeypatch, publisher, artifacts)
    if problem == "missing":
        fake.release["assets"].pop()
    elif problem == "draft":
        fake.release["draft"] = True
    elif problem == "duplicate":
        fake.release["assets"][1] = fake.release["assets"][0]
    elif problem == "uploading":
        fake.release["assets"][0]["state"] = "starter"
    elif problem == "tag":
        fake.tag["object"]["sha"] = "c" * 40
    elif problem == "annotated":
        fake.tag["object"]["type"] = "tag"
    elif problem == "hash":
        fake.blobs["api"] = b"different"
        fake.populate_assets()
    elif problem == "size":
        fake.release["assets"][0]["size"] += 1
    elif problem == "digest":
        fake.release["assets"][0]["digest"] = "sha256:" + "0" * 64
    elif problem == "manifest_size":
        fake.release["assets"][2]["size"] += 1
    assert cli(publisher, "--publish", "--directory", str(artifacts)) == 1
    assert not fake.mutations


def test_new_release_validated_while_draft_before_publication(monkeypatch, publisher, artifacts):
    fake = install(monkeypatch, publisher, artifacts, exists=False)
    assert cli(publisher, "--publish", "--directory", str(artifacts)) == 0
    assert fake.release["draft"] is False
    assert len(fake.mutations) == 3
    patch_index = next(index for index, call in enumerate(fake.calls) if "PATCH" in call)
    downloads = [index for index, call in enumerate(fake.calls) if "/releases/assets/" in " ".join(call)]
    assert len([index for index in downloads if index < patch_index]) == 3
    assert len([index for index in downloads if index > patch_index]) == 3
    assert all("--clobber" not in call for call in fake.calls)
    # A second invocation must reuse the first result without any further writes.
    assert cli(publisher, "--publish", "--directory", str(artifacts)) == 0
    assert len(fake.mutations) == 3


@pytest.mark.parametrize("problem", ["hash", "commit", "tree", "missing", "missing_size", "bool_size", "extra_asset", "json"])
def test_invalid_local_artifacts_fail_before_github(monkeypatch, publisher, artifacts, problem):
    fake = install(monkeypatch, publisher, artifacts, exists=False)
    path = artifacts / "release.json"
    manifest = json.loads(path.read_bytes())
    if problem == "hash":
        (artifacts / "api").write_bytes(b"changed")
    elif problem in {"commit", "tree"}:
        manifest[problem] = "c" * 40
    elif problem == "missing":
        (artifacts / "app.tar.gz").unlink()
    elif problem == "missing_size":
        manifest["assets"]["api"].pop("size")
    elif problem == "bool_size":
        manifest["assets"]["api"]["size"] = True
    elif problem == "extra_asset":
        manifest["assets"]["another"] = manifest["assets"]["api"]
    path.write_bytes(b"not json" if problem == "json" else json.dumps(manifest).encode())
    assert cli(publisher, "--publish", "--directory", str(artifacts)) == 1
    assert not fake.calls


@pytest.mark.parametrize("failure", ["upload", "download"])
def test_failed_publication_leaves_draft_for_explicit_repair(monkeypatch, publisher, artifacts, failure, capsys):
    fake = install(monkeypatch, publisher, artifacts, exists=False)
    fake.fail_upload = failure == "upload"
    fake.fail_download = failure == "download"
    assert cli(publisher, "--publish", "--directory", str(artifacts)) == 1
    assert fake.release["draft"] is True
    assert not any("PATCH" in call for call in fake.calls)
    assert not any("--clobber" in call or "delete" in call for call in fake.calls)
    captured = capsys.readouterr()
    assert "repair needed" in captured.err
    assert "secret" not in captured.err
    assert cli(publisher, "--publish", "--directory", str(artifacts)) == 1
    assert len(fake.mutations) == 2


def test_orphaned_wrong_tag_is_not_overwritten(monkeypatch, publisher, artifacts):
    fake = install(monkeypatch, publisher, artifacts, exists=False)
    fake.tag = {"object": {"type": "commit", "sha": "c" * 40}}
    assert cli(publisher, "--publish", "--directory", str(artifacts)) == 1
    assert not fake.mutations


def test_invalid_arguments_fail_before_github(monkeypatch, publisher, artifacts):
    fake = install(monkeypatch, publisher, artifacts)
    for repository, sha, tree in [("../repo", SHA, TREE), (REPOSITORY, "a" * 39, TREE), (REPOSITORY, SHA, "x" * 40)]:
        with pytest.raises(publisher.PublicationError):
            publisher.publish(repository, sha, tree, None)
    assert not fake.calls


@pytest.mark.parametrize("arguments", [("--publish",), ("--check", "--directory", "/tmp")])
def test_directory_only_allowed_for_publish(publisher, arguments):
    with pytest.raises(SystemExit, match="2"):
        cli(publisher, *arguments)


@pytest.mark.parametrize("response", [
    {"errors": [{"message": "private response"}]},
    {"data": {"repository": None}},
    {"data": {"repository": {"release": {"databaseId": "invalid"}}}},
])
def test_missing_rest_release_requires_successful_draft_lookup(monkeypatch, publisher, artifacts, response, capsys):
    fake = FakeGitHub(artifacts, exists=False)
    def run(command, **kwargs):
        if "graphql" in command:
            return subprocess.CompletedProcess(command, 0, json.dumps(response).encode(), b"")
        return fake(command, **kwargs)
    monkeypatch.setattr(publisher.subprocess, "run", run)
    assert cli(publisher, "--check") == 1
    assert not fake.mutations
    captured = capsys.readouterr()
    assert "reusable=false" not in captured.out
    assert "private response" not in captured.err


def test_check_finds_unpublished_draft_without_mutations(monkeypatch, publisher, artifacts):
    fake = install(monkeypatch, publisher, artifacts)
    fake.release["draft"] = True
    assert cli(publisher, "--check") == 1
    assert any("graphql" in call for call in fake.calls)
    assert any(call[-1].endswith("releases/7") for call in fake.calls)
    assert not fake.mutations
