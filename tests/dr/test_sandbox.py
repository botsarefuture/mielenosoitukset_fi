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
    names = ["app.tar.gz", "mongo.archive.gz", "requirements.lock", "build_sha", "browser-assets.tar.gz", "wheels/example.whl"]
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


def test_snapshot_polish_finishes_redirects_lists_contact_and_mobile_navigation(tmp_path, monkeypatch):
    module = load("polish_snapshot")
    for rel, content in {
        "index.html": '<main><h1>Etusivu</h1><img src="https://external.invalid/tracker.png"><img src="relative-missing.png"><a href="#dr-unavailable">Ilmoita mielenosoituksesta</a><div id="featured-demos-grid"></div></main>',
        "demonstrations/index.html": '<main><h1>Tapahtumat</h1><section><div id="demos-grid"></div>Edellinen Näytä lisää</section></main>',
        "contact/index.html": '<main><h1>Yhteystiedot</h1><section id="contact-form-section"><p>Täytä lomake</p></section></main>',
        "redirect/index.html": '<title>Redirecting...</title><a href="/mirror/contact/">continue</a>',
        "cities/index.html": '<main><h1>Kaupungit</h1><a href="/mirror/missing/">Missing</a></main>',
        "ohjeet/index.html": '<main><h1>Ohjeet</h1></main>',
        "info/index.html": '<main><h1>Tietoa</h1></main>',
        "privacy/index.html": '<main><h1>Tietosuoja</h1></main>',
    }.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    event = {"_id": "abc123", "title": "Public event", "description": '<script>bad()</script><p>Event text</p>',
             "formatted_date": "19.10.2026", "start_time": "12:00", "city": "Helsinki", "address": "Square"}
    report = module.polish(tmp_path, {"results": [event], "snapshot_captured_at": "2026-10-19T15:00:00+00:00"}, ROOT / "scripts/dr/snapshot.css")
    assert report["events"] == 1 and report["redirect_stubs_replaced"] == 1
    for p in tmp_path.rglob('*.html'):
        page = module.soup(p.read_text())
        assert not page.select('script, form, iframe')
        assert page.select_one('nav[aria-label="Päävalikko"]')
        assert page.select_one('meta[name="robots"]')['content'] == 'noindex, nofollow'
        assert 'Redirecting...' not in page.get_text()
        for a in page.find_all('a', href=True):
            if a['href'].startswith('/mirror/'):
                assert module.local_target(tmp_path, a['href']).is_file(), a['href']
    assert 'Public event' in (tmp_path / 'index.html').read_text()
    assert 'external.invalid' not in (tmp_path / 'index.html').read_text()
    assert 'Ilmoittaminen tauolla' in (tmp_path / 'index.html').read_text()
    assert 'relative-missing.png' not in (tmp_path / 'index.html').read_text()
    assert 'Viestien lähetys on tauolla' in (tmp_path / 'contact/index.html').read_text()
    assert 'Näytä lisää' not in (tmp_path / 'demonstrations/index.html').read_text()
    assert '19.10.2026 18.00' in (tmp_path / 'index.html').read_text()
    module.polish(tmp_path, {"results": [event], "snapshot_captured_at": "2026-10-19T15:00:00+00:00"}, ROOT / "scripts/dr/snapshot.css")
    page = module.soup((tmp_path / 'index.html').read_text())
    assert len(page.select('.dr-banner')) == 1
    assert len(page.select('link[href="/mirror/dr-snapshot.css"]')) == 1
    assert len(page.select('nav[aria-label="Päävalikko"]')) == 1
    monkeypatch.syspath_prepend(str(ROOT / 'scripts/dr'))
    verifier = load('verify_snapshot')
    assert verifier.verify(tmp_path)['broken_resources'] == 0
    (tmp_path / 'dr-snapshot.css').unlink()
    with pytest.raises(ValueError, match='Missing'):
        verifier.verify(tmp_path)



def test_snapshot_url_resolution_prevents_traversal_and_handles_encoded_names(tmp_path):
    module = load("polish_snapshot")
    (tmp_path / 'city name').mkdir()
    (tmp_path / 'city name/index.html').write_text('Public')
    assert module.local_target(tmp_path, '/mirror/city%20name/') == tmp_path / 'city name/index.html'
    assert module.local_target(tmp_path, '/mirror/%2e%2e/private') is None
    assert module.local_target(tmp_path, 'https://elsewhere.invalid/mirror/page') is None


def control_profile():
    return {'ssh_destination': 'recovery-test-alias', 'expected_hostname': 'test-recovery-host',
            'python_path': '/opt/test-venv/bin/python', 'toolkit_path': '/opt/test-toolkit',
            'bundle_path': '/private/test-bundle'}


def test_independent_control_rejects_arbitrary_commands_and_production_targets():
    module = load('recovery_control')
    with pytest.raises(ValueError):
        module.command_for('rehearse; rm -rf /', control_profile())
    command = module.command_for('rehearse', control_profile())
    assert 'recovery-test-alias' in command
    assert 'StrictHostKeyChecking=yes' in command
    assert 'flock -n' in command[-1]
    assert 'lc-main' not in command[-1]
    assert 'test-recovery-host' in command[-1]


def test_independent_panel_checks_host_origin_csrf_and_action(tmp_path):
    import http.client
    import threading
    from http.server import ThreadingHTTPServer
    from urllib.parse import urlencode
    module = load('recovery_control')
    recovery = module.Recovery(tmp_path / 'private', control_profile())
    started = []
    recovery.start = lambda action: started.append(action) or True if action in module.COMMANDS else (_ for _ in ()).throw(ValueError())
    server = ThreadingHTTPServer(('127.0.0.1', 0), module.handler_for(recovery))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = 'http://127.0.0.1:' + str(server.server_port)
    def request(path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', server.server_port)
        conn.request('POST' if body is not None else 'GET', path, body=body, headers=headers or {})
        response = conn.getresponse()
        code = response.status
        response.read()
        conn.close()
        return code
    try:
        assert request('/') == 200
        body = urlencode({'action': 'rehearse', 'csrf': recovery.token})
        assert request('/run', body, {'Origin': 'https://evil.invalid'}) == 403
        assert request('/run', body, {'Host': 'evil.invalid', 'Origin': origin}) == 403
        assert request('/run', urlencode({'action': 'rehearse', 'csrf': 'wrong'}), {'Origin': origin}) == 403
        assert request('/run', urlencode({'action': 'unknown', 'csrf': recovery.token}), {'Origin': origin}) == 400
        assert not started
        assert request('/run', body, {'Origin': origin}) == 202
        assert started == ['rehearse']
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_independent_panel_blocks_overlapping_jobs(tmp_path, monkeypatch):
    import threading
    module = load('recovery_control')
    recovery = module.Recovery(tmp_path / 'private', control_profile())
    entered = threading.Event()
    release = threading.Event()
    def run(action):
        entered.set()
        release.wait(timeout=3)
    monkeypatch.setattr(recovery, 'run', run)
    try:
        assert recovery.start('rehearse')
        assert entered.wait(timeout=1)
        assert not recovery.start('rehearse')
    finally:
        release.set()


def test_recovery_profile_is_private_and_rejects_unsafe_connection_settings(tmp_path):
    import json
    module = load('recovery_control')
    path = tmp_path / 'private.json'
    profile = control_profile()
    path.write_text(json.dumps(profile))
    path.chmod(0o644)
    with pytest.raises(ValueError, match='mode 600'):
        module.load_profile(path)
    path.chmod(0o600)
    assert module.load_profile(path)['ssh_destination'] == 'recovery-test-alias'
    profile['ssh_destination'] = '-oProxyCommand=bad'
    path.write_text(json.dumps(profile))
    with pytest.raises(ValueError, match='ssh_destination'):
        module.load_profile(path)
    profile = control_profile()
    profile['bundle_path'] = '/private/test\ninvalid'
    path.write_text(json.dumps(profile))
    with pytest.raises(ValueError, match='bundle_path'):
        module.load_profile(path)


def test_snapshot_resolution_rejects_absolute_paths_and_symlink_escape(tmp_path):
    module = load('polish_snapshot')
    root = tmp_path / 'public'
    root.mkdir()
    outside = tmp_path / 'private.html'
    outside.write_text('<main>PRIVATE</main>')
    (root / 'escape.html').symlink_to(outside)
    for url in ['/mirror//etc/passwd', '/mirror/%2Fetc/passwd', '/mirror/%5cprivate', '/mirror/escape.html']:
        assert module.local_target(root, url) is None


def test_snapshot_requires_honest_timezone_aware_capture_time(tmp_path):
    module = load('polish_snapshot')
    for stamp in [None, '', '2026-10-19T12:00:00']:
        with pytest.raises(ValueError, match='snapshot_captured_at'):
            module.polish(tmp_path, {'results': [], 'snapshot_captured_at': stamp}, ROOT / 'scripts/dr/snapshot.css')


def test_recovery_timeout_keeps_partial_diagnostics_and_unknown_remote_state(tmp_path, monkeypatch):
    import subprocess
    module = load('recovery_control')
    recovery = module.Recovery(tmp_path / 'private', control_profile())
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('ssh', 600, output=b'restore started', stderr=b'connection lost')
    monkeypatch.setattr(module.subprocess, 'run', timeout)
    recovery.run('rehearse')
    result = recovery.snapshot()
    assert result['status'] == 'failed'
    assert result['remote_state'] == 'unknown'
    assert 'restore started' in result['output'] and 'connection lost' in result['output']


def test_snapshot_filters_saved_events_by_city_tag_and_capture_day():
    from datetime import datetime
    module = load('polish_snapshot')
    events = [{'title': 'Today', 'city': 'Hämeenlinna', 'tags': ['Ilmasto'], 'date': '2026-10-19'},
              {'title': 'Later', 'city': 'Helsinki', 'tags': ['Muu'], 'date': '2026-10-23'}]
    captured = datetime.fromisoformat('2026-10-19T12:00:00+00:00')
    assert module.selected_events(events, 'city/hameenlinna/index.html', captured) == [events[0]]
    assert module.selected_events(events, 'tag/ilmasto/index.html', captured) == [events[0]]
    assert module.selected_events(events, 'mielenosoitukset-tanaan/index.html', captured) == [events[0]]
    assert module.selected_events(events, 'city/helsinki/tanaan/index.html', captured) == []


def test_recovery_reports_audit_failure_instead_of_silent_success(tmp_path, monkeypatch):
    from types import SimpleNamespace
    module = load('recovery_control')
    recovery = module.Recovery(tmp_path / 'private', control_profile())
    monkeypatch.setattr(module.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout='ok', stderr=''))
    def denied(*args, **kwargs):
        raise PermissionError('audit unavailable')
    monkeypatch.setattr(module.os, 'open', denied)
    recovery.run('status')
    assert recovery.snapshot()['status'] == 'audit_failed'
    assert recovery.snapshot()['audit_error'] == 'PermissionError'


def test_specific_browser_css_alias_is_rewritten_before_generic_package_url():
    module = load('copy_urls')
    value = module.rewrite('<link href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css"><script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>')
    assert '/static/dr-vendor/flatpickr-4.6.13.min.css' in value
    assert '/static/dr-vendor/flatpickr-4.6.13.min.js' in value
    assert '.min.js/dist' not in value
    unknown_locale = 'https://cdn.jsdelivr.net/npm/flatpickr/dist/l10n/fi.js'
    assert module.rewrite(unknown_locale) == unknown_locale


def test_browser_assets_pack_only_hash_verified_named_files(tmp_path):
    import hashlib,tarfile
    module = load('vendor_assets')
    root = tmp_path / 'assets'
    root.mkdir()
    data = b'fixture browser asset'
    (root / 'asset.js').write_bytes(data)
    module.ASSETS = {'asset.js': ('https://example.invalid/asset.js', hashlib.sha256(data).hexdigest())}
    archive = tmp_path / 'browser-assets.tar.gz'
    module.pack_assets(root, archive)
    with tarfile.open(archive, 'r:gz') as files:
        assert files.getnames() == ['asset.js']
        assert files.extractfile('asset.js').read() == data
    (root / 'asset.js').write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='checksum mismatch'):
        module.pack_assets(root, archive)


def test_browser_archive_rejects_empty_incomplete_and_duplicate_assets(monkeypatch):
    import tarfile
    monkeypatch.syspath_prepend(str(ROOT / 'scripts/dr'))
    module = load('rehearse_bundle')
    monkeypatch.setattr(module, 'ASSETS', {'asset.js': ('https://example.invalid/asset.js', 'fixture')})
    good = tarfile.TarInfo('asset.js')
    module.validate_browser_members([good])
    for members in [[], [tarfile.TarInfo('unexpected.js')], [good, good]]:
        with pytest.raises(ValueError, match='complete pinned asset set'):
            module.validate_browser_members(members)
