import importlib.util
from pathlib import Path
import stat

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / "dr" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_new_secrets_and_loopback_dependencies(tmp_path):
    config = load("write_config")
    first, second = config.configuration(), config.configuration()
    assert first["SECRET_KEY"] != second["SECRET_KEY"]
    assert first["S3"]["SECRET_KEY"] != second["S3"]["SECRET_KEY"]
    assert first["MONGO_URI"].startswith("mongodb://127.0.0.1:")
    assert first["MAIL"]["SERVER"] == "127.0.0.1"
    assert first["S3"]["ENDPOINT_URI"].startswith("http://127.0.0.1:")
    assert first["ENABLE_EMAIL_WORKER"] is False
    assert first["ENABLE_BACKGROUND_JOBS"] is False
    assert first["ENABLE_PANIC_THREAD"] is False
    assert first["TICKET_INGRESS_ENABLED"] is False
    assert first["DEBUG"] is False
    target = tmp_path / "config.yaml"
    config.write_config(target)
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        config.write_config(target)


def test_snapshot_disables_writes_and_rewrites_local_urls(tmp_path):
    module = load("prepare_snapshot")
    mirror = module.Mirror(tmp_path)
    (tmp_path / "cities").mkdir()
    (tmp_path / "cities" / "index.html").write_text("Cities")
    fetched = []
    mirror.asset = lambda url, rel: fetched.append(rel)
    parser = module.StaticHTML(mirror, module.SOURCE + "/cities/")
    parser.feed('<body onload="send()"><script>fetch("https://example.org")</script>'
                '<link rel="preconnect" href="https://cdn2.mielenosoitukset.fi">'
                '<form action="https://example.org"><input name="email"><button>Send</button></form>'
                '<a href="/submit">Submit</a><a href="/cities/">Cities</a>'
                '<link rel="stylesheet" href="/static/app.css">'
                '<img src="https://cdn2.mielenosoitukset.fi/public.jpg"></body>')
    output = "".join(parser.output)
    assert "<script" not in output and "<form" not in output
    assert "onload" not in output and "<input" not in output
    assert 'href="/mirror/cities/"' in output
    assert 'href="#dr-unavailable"' in output
    assert "/mirror/_external/cdn2.mielenosoitukset.fi/public.jpg" in output
    assert "TEST / DR SNAPSHOT" in output
    assert "static/app.css" in fetched
    assert "_external/cdn2.mielenosoitukset.fi/index.html" not in fetched


def test_asset_cannot_escape_snapshot_directory():
    module = load("prepare_snapshot")
    for url in [module.SOURCE + "/../private", module.SOURCE + "/%2e%2e/private", module.SOURCE + "/%2fetc/passwd"]:
        with pytest.raises(ValueError):
            module.destination(url)


def test_mirrored_css_and_links_survive_a_second_pass(tmp_path, monkeypatch):
    module = load("prepare_snapshot")
    css = tmp_path / "static" / "app.css"
    css.parent.mkdir()
    original = 'body{background:url("/mirror/static/image.png")}'
    css.write_text(original)
    def unexpected_network(*args, **kwargs):
        raise AssertionError("Previously mirrored asset must not be downloaded again")
    monkeypatch.setattr(module.subprocess, "run", unexpected_network)
    for _ in range(2):
        mirror = module.Mirror(tmp_path)
        mirror.asset(module.SOURCE + "/static/app.css", "static/app.css")
        assert css.read_text() == original
        assert mirror.link("/mirror/cities/", module.SOURCE) == "/mirror/cities/"


def test_backup_preserves_the_applications_authentication_database():
    module = load("backup_database")
    assert module.authentication_database("mongodb://example.invalid") == "admin"
    assert module.authentication_database("mongodb://example.invalid/other") == "other"
    assert module.authentication_database("mongodb://example.invalid/other?authSource=accounts") == "accounts"


def test_guest_export_rejects_production_ids_before_running_commands(monkeypatch):
    module = load("prepare_guest")
    def forbidden(*args):
        raise AssertionError("No command may run for a production VM")
    monkeypatch.setattr(module, "command", forbidden)
    for vmid in ["100", "101", "102", "999"]:
        with pytest.raises(ValueError):
            module.prepare(vmid)


def test_explicit_smtp_sender_cannot_bypass_capture():
    from types import SimpleNamespace
    module = load("capture_delivery")
    config = SimpleNamespace(MAIL_SERVER="127.0.0.1", MAIL_PORT=1025,
                             MAIL_USERNAME="sandbox", MAIL_PASSWORD="test-only")
    sender = SimpleNamespace(email_server="production.example.invalid", email_port=587,
                             username="production", password="do-not-use", profile="ticket")
    result = module.delivery_settings(config, sender)
    assert result["smtp_server"] == "127.0.0.1" and result["smtp_port"] == 1025
    assert result["smtp_password"] == "test-only"
    assert result["use_tls"] is False
    config.MAIL_SERVER = "production.example.invalid"
    with pytest.raises(RuntimeError):
        module.delivery_settings(config, sender)


def test_api_and_html_urls_stay_on_sandbox():
    module = load("copy_urls")
    result = module.rewrite({"results": [{"img": "https://cdn2.mielenosoitukset.fi/DEM/test.jpg",
                                         "detail": "https://mielenosoitukset.fi/demonstration/1"}],
                             "count": 1})
    assert result["results"][0]["img"] == "https://pentest.mielenosoitukset.fi/media/DEM/test.jpg"
    assert result["results"][0]["detail"] == "https://pentest.mielenosoitukset.fi/demonstration/1"
    assert result["count"] == 1


def test_release_archive_rejects_secrets_links_and_path_escape(monkeypatch):
    import sys
    import tarfile
    monkeypatch.syspath_prepend(str(ROOT / "scripts/dr"))
    module = load("rehearse_bundle")
    for name in ["../private", "/etc/private", "nested/.env", "nested/.env.production", "config.yaml"]:
        with pytest.raises(ValueError):
            module.validate_member(tarfile.TarInfo(name))
    member = tarfile.TarInfo("link")
    member.type = tarfile.SYMTYPE
    member.linkname = "../../private"
    with pytest.raises(ValueError):
        module.validate_member(member)
    module.validate_member(tarfile.TarInfo("application/code.py"))


def test_media_permission_failure_is_explicit_and_later_objects_are_saved(tmp_path, monkeypatch):
    import hashlib
    import io
    import json
    import tarfile
    from types import SimpleNamespace
    from botocore.exceptions import ClientError
    import boto3
    module = load("backup_media")
    objects = [{"Key": key, "Size": 4, "ETag": '"test"'} for key in ["first.css", "denied.jpg", "last.jpg"]]
    class Client:
        def get_paginator(self, name):
            return SimpleNamespace(paginate=lambda **kwargs: [{"Contents": objects}])
        def get_object(self, **kwargs):
            if kwargs["Key"] == "denied.jpg":
                raise ClientError({"Error": {"Code": "AccessDenied"},
                                   "ResponseMetadata": {"HTTPStatusCode": 403}}, "GetObject")
            return {"Body": io.BytesIO(b"test"), "ContentType": "custom/test", "ContentEncoding": "gzip"}
    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: Client())
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    config = tmp_path / "config.yaml"
    config.write_text(json.dumps({"S3": {"ACCESS_KEY": "test-only", "SECRET_KEY": "test-only",
                                        "ENDPOINT_URI": "https://example.invalid"}}))
    stream = io.BytesIO()
    with monkeypatch.context() as patch:
        patch.setattr(module.sys, "stdout", SimpleNamespace(buffer=stream))
        result = module.backup(config)
    assert result == 2
    stream.seek(0)
    with tarfile.open(fileobj=stream, mode="r:") as archive:
        manifest = json.load(archive.extractfile(".dr-media-manifest.json"))
        assert manifest["complete"] is False
        assert manifest["unavailable_objects"] == [{"key": "denied.jpg", "status": "403"}]
        assert [obj["key"] for obj in manifest["objects"]] == ["first.css", "last.jpg"]
        assert archive.getmember("first.css").pax_headers["dr.content_encoding"] == "gzip"
        assert manifest["objects"][0]["sha256"] == hashlib.sha256(b"test").hexdigest()


def test_bundle_verification_requires_every_artifact_and_detects_tampering(tmp_path, monkeypatch):
    import hashlib
    import json
    monkeypatch.syspath_prepend(str(ROOT / "scripts/dr"))
    module = load("rehearse_bundle")
    (tmp_path / "wheels").mkdir()
    names = ["app.tar.gz", "mongo.archive.gz", "requirements.lock", "build_sha", "wheels/example.whl"]
    for name in names:
        (tmp_path / name).write_bytes(b"fixture")
    hashes = {name: hashlib.sha256(b"fixture").hexdigest() for name in names}
    manifest = tmp_path / "SHA256SUMS.json"
    manifest.write_text(json.dumps({k: v for k, v in hashes.items() if k != "app.tar.gz"}))
    with pytest.raises(ValueError, match="omits"):
        module.verify_bundle(tmp_path)
    manifest.write_text(json.dumps(hashes))
    module.verify_bundle(tmp_path)
    (tmp_path / "mongo.archive.gz").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="integrity failure"):
        module.verify_bundle(tmp_path)


def test_inline_style_dependencies_are_mirrored(tmp_path):
    module = load("prepare_snapshot")
    mirror = module.Mirror(tmp_path)
    fetched = []
    mirror.asset = lambda url, rel: fetched.append(rel)
    parser = module.StaticHTML(mirror, module.SOURCE + "/city/test/")
    parser.feed('<style>body{background:url(/static/test.png)}</style><p>url(/ordinary-text)</p>')
    output = "".join(parser.output)
    assert 'url("/mirror/static/test.png")' in output
    assert "url(/ordinary-text)" in output
    assert fetched == ["static/test.png"]


def test_rehearsal_cleanup_continues_when_database_drop_fails(tmp_path, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.syspath_prepend(str(ROOT / "scripts/dr"))
    module = load("rehearse_bundle")
    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "secret.yaml").write_text("test-only")
    log = (tmp_path / "private.log").open("w")
    closed = []
    def unavailable(database):
        raise RuntimeError("Database temporarily unavailable")
    client = SimpleNamespace(drop_database=unavailable, close=lambda: closed.append(True))
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: None)
    errors = module.cleanup_rehearsal(client, "dr_verify_test", stage, "dr-verify-test", log)
    assert errors == {"drop_database": "RuntimeError"}
    assert not stage.exists() and log.closed and closed == [True]


def test_public_pentest_keeps_indexing_and_file_exposure_guards():
    config = (ROOT / "scripts/dr/nginx.conf").read_text()
    assert 'auth_basic off;' in config
    assert 'auth_basic_user_file' not in config
    assert 'add_header X-Robots-Tag "noindex, nofollow" always;' in config
    assert 'Disallow: /' in config
    assert 'location ~ /\\. { deny all; }' in config
    assert 'limit_except GET HEAD { deny all; }' in config


def test_admin_dependencies_stay_local_without_weakening_csp():
    urls = load("copy_urls")
    installer = load("vendor_assets")
    for name, (url, digest) in installer.ASSETS.items():
        rendered = urls.rewrite('<script src="' + url + '"></script>')
        assert url not in rendered
        assert '/static/dr-vendor/' + name in rendered
        assert len(digest) == 64
    policy = (ROOT / "scripts/dr/nginx-app.conf").read_text()
    assert "script-src 'self' 'unsafe-inline';" in policy


def test_vendor_installer_rejects_corruption_before_replacing_asset(tmp_path, monkeypatch):
    import io
    module = load("vendor_assets")
    module.ASSETS = {"asset.js": ("https://example.invalid/asset.js", "0" * 64)}
    monkeypatch.setattr(module, "urlopen", lambda *args, **kwargs: io.BytesIO(b"wrong"))
    with pytest.raises(ValueError, match="checksum mismatch"):
        module.install(tmp_path)
    assert not (tmp_path / "asset.js").exists()
