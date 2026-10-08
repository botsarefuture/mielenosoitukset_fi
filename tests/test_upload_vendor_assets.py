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


@pytest.mark.parametrize("prefix", ["vendor/bootstrap/5.3.0", "vendor/web-vitals/6.2.2"])
@pytest.mark.parametrize("apply", [False, True])
def test_selected_manifest_controls_uploads_and_content_types(monkeypatch, tmp_path, prefix, apply):
    from copy import deepcopy
    from unittest.mock import Mock

    # Keep each real manifest's filenames and types; use synthetic trusted bytes.
    manifests = deepcopy(upload_vendor_assets.VENDOR_MANIFESTS)
    selected = manifests[prefix]
    for filename, specification in selected.items():
        content = f"fixture:{prefix}/{filename}".encode()
        (tmp_path / filename).write_bytes(content)
        specification["sha256"] = upload_vendor_assets.sha256(content)
    (tmp_path / "unlisted.js").write_text("must not be uploaded")
    monkeypatch.setattr(upload_vendor_assets, "VENDOR_MANIFESTS", manifests)
    client = Mock()
    client.exceptions.ClientError = ClientError
    client.head_object.side_effect = ClientError({"Error": {"Code": "NoSuchKey"}}, "HeadObject")
    monkeypatch.setattr(upload_vendor_assets.boto3, "client", Mock(return_value=client))

    args = [str(tmp_path), "--prefix", f"/{prefix}/"]
    if apply:
        args.append("--apply")
    assert upload_vendor_assets.main(args) == 0
    assert {entry.kwargs["Key"] for entry in client.head_object.call_args_list} == {
        f"{prefix}/{filename}" for filename in selected
    }
    if not apply:
        client.put_object.assert_not_called()
        return
    assert client.put_object.call_count == len(selected)
    for entry in client.put_object.call_args_list:
        fields = entry.kwargs
        filename = fields["Key"].removeprefix(f"{prefix}/")
        assert fields == {
            "Bucket": upload_vendor_assets.Config.S3_BUCKET,
            "Key": f"{prefix}/{filename}", "Body": (tmp_path / filename).read_bytes(),
            "ContentType": selected[filename]["content_type"],
            "CacheControl": "public, max-age=31536000, immutable",
            "Metadata": {"sha256": selected[filename]["sha256"]}, "IfNoneMatch": "*",
        }


def test_selected_manifest_requires_its_license_before_s3_access(monkeypatch, tmp_path):
    from unittest.mock import Mock

    (tmp_path / "web-vitals.iife.js").write_text("fixture")
    client_factory = Mock()
    monkeypatch.setattr(upload_vendor_assets.boto3, "client", client_factory)
    with pytest.raises(SystemExit) as error:
        upload_vendor_assets.main([str(tmp_path), "--prefix", "vendor/web-vitals/6.2.2", "--apply"])
    assert error.value.code == 2
    client_factory.assert_not_called()
