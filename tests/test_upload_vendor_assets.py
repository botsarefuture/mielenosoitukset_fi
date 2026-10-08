import importlib.util
from pathlib import Path

import pytest
from botocore.exceptions import ClientError


_SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "upload_vendor_assets.py"
_SPEC = importlib.util.spec_from_file_location("upload_vendor_assets_script", _SCRIPT_PATH)
upload_vendor_assets = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(upload_vendor_assets)


TEST_PREFIX = "vendor/test/1.0.0"


def _write_expected_assets(asset_dir: Path):
    manifest = {}
    for name in ("asset.js", "LICENSE"):
        content = f"test:{name}".encode()
        (asset_dir / name).write_bytes(content)
        manifest[name] = {
            "content_type": "application/javascript" if name.endswith(".js") else "text/plain",
            "sha256": upload_vendor_assets.sha256(content),
        }
    return {TEST_PREFIX: manifest}


def test_existing_object_without_matching_hash_is_never_overwritten(
    monkeypatch, tmp_path
):
    manifests = _write_expected_assets(tmp_path)
    monkeypatch.setattr(upload_vendor_assets, "VENDOR_MANIFESTS", manifests)

    class FakeClient:
        class exceptions:
            ClientError = RuntimeError

        def __init__(self):
            self.uploaded = []

        def head_object(self, **kwargs):
            return {"Metadata": {}}

        def put_object(self, *args, **kwargs):
            self.uploaded.append((args, kwargs))

    client = FakeClient()
    monkeypatch.setattr(upload_vendor_assets.boto3, "client", lambda *a, **k: client)

    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        upload_vendor_assets.main(
            [str(tmp_path), "--prefix", TEST_PREFIX, "--apply"]
        )

    assert client.uploaded == []


def test_prefix_validation_finishes_before_any_missing_asset_is_uploaded(
    monkeypatch, tmp_path
):
    manifests = _write_expected_assets(tmp_path)
    monkeypatch.setattr(upload_vendor_assets, "VENDOR_MANIFESTS", manifests)

    class FakeClient:
        class exceptions:
            ClientError = ClientError

        def __init__(self):
            self.lookups = 0
            self.uploaded = []

        def head_object(self, **kwargs):
            self.lookups += 1
            if self.lookups == 1:
                raise ClientError(
                    {"Error": {"Code": "404", "Message": "missing"}},
                    "HeadObject",
                )
            return {"Metadata": {"sha256": "different"}}

        def put_object(self, *args, **kwargs):
            self.uploaded.append((args, kwargs))

    client = FakeClient()
    monkeypatch.setattr(upload_vendor_assets.boto3, "client", lambda *a, **k: client)

    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        upload_vendor_assets.main(
            [str(tmp_path), "--prefix", TEST_PREFIX, "--apply"]
        )

    assert client.uploaded == []


def test_untrusted_vendor_content_is_rejected_before_s3_lookup(monkeypatch, tmp_path):
    manifests = _write_expected_assets(tmp_path)
    manifests[TEST_PREFIX]["asset.js"]["sha256"] = "0" * 64
    monkeypatch.setattr(upload_vendor_assets, "VENDOR_MANIFESTS", manifests)

    class FakeClient:
        class exceptions:
            ClientError = ClientError

        def head_object(self, **kwargs):
            raise AssertionError("untrusted files must fail before S3 lookup")

    monkeypatch.setattr(
        upload_vendor_assets.boto3,
        "client",
        lambda *args, **kwargs: FakeClient(),
    )

    with pytest.raises(RuntimeError, match="untrusted vendor content"):
        upload_vendor_assets.main(
            [str(tmp_path), "--prefix", TEST_PREFIX, "--apply"]
        )


def test_only_explicit_versioned_manifests_are_accepted(tmp_path):
    _write_expected_assets(tmp_path)

    with pytest.raises(SystemExit):
        upload_vendor_assets.main(
            [str(tmp_path), "--prefix", "vendor/untrusted/9.9.9"]
        )
