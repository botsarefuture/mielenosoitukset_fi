from pathlib import Path

import pytest
from botocore.exceptions import ClientError

from scripts import upload_vendor_assets


def _write_expected_assets(asset_dir: Path):
    for name in upload_vendor_assets.ALLOWED_FILES:
        (asset_dir / name).write_bytes(f"test:{name}".encode())


def test_existing_object_without_matching_hash_is_never_overwritten(
    monkeypatch, tmp_path
):
    _write_expected_assets(tmp_path)

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
            [str(tmp_path), "--prefix", "vendor/bootstrap/5.3.0", "--apply"]
        )

    assert client.uploaded == []


def test_prefix_validation_finishes_before_any_missing_asset_is_uploaded(
    monkeypatch, tmp_path
):
    _write_expected_assets(tmp_path)

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
            [str(tmp_path), "--prefix", "vendor/bootstrap/5.3.0", "--apply"]
        )

    assert client.uploaded == []
