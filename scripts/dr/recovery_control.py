#!/usr/bin/env python3
"""Independent localhost operator panel for the existing isolated DR host.

Runs on an operator laptop with its existing SSH key and known_hosts. Nothing
executes on lc-main and no production routing changes are available. The current
restore action verifies app+DB on an already prepared host; it is not bare-host
provisioning or production promotion. Python's standard library is sufficient.
"""
from datetime import datetime, timezone
import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import re
import shlex
import stat
import subprocess
import threading
from urllib.parse import parse_qs

PORT = 18850
COMMANDS = {
    'status': "systemctl is-active dr-app dr-mongodb dr-mailpit dr-s3 nginx && curl -fsS http://127.0.0.1:5002/health",
    'rehearse': 'configured-bundle',
}


def load_profile(path):
    info = path.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError('Private profile must be owned by you with mode 600')
    profile = json.loads(path.read_text())
    for name in ['ssh_destination', 'expected_hostname']:
        if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.@-]*', profile.get(name, '')):
            raise ValueError('Invalid ' + name)
    for name in ['python_path', 'toolkit_path', 'bundle_path']:
        value = profile.get(name, '')
        if not value.startswith('/') or '..' in Path(value).parts or '\n' in value:
            raise ValueError('Invalid ' + name)
    if profile.get("ssh_config"):
        private = Path(profile["ssh_config"])
        metadata = private.stat()
        if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
            raise ValueError("SSH config must be private and owned by you")
    return profile


def command_for(action, profile):
    if action not in COMMANDS:
        raise ValueError('Unknown recovery action')
    remote = COMMANDS[action]
    if action == 'rehearse':
        remote = 'flock -n /run/lock/mielenosoitukset-dr-rehearsal.lock ' + ' '.join(map(shlex.quote, [profile['python_path'], str(Path(profile['toolkit_path']) / 'scripts/dr/rehearse_bundle.py'), profile['bundle_path']]))
    ssh_config = ['-F', profile['ssh_config']] if profile.get('ssh_config') else []
    return ['ssh', *ssh_config, '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'ConnectTimeout=10', profile['ssh_destination'],
            'test "$(hostname)" = ' + shlex.quote(profile['expected_hostname']) + ' && ' + remote]


class Recovery:
    def __init__(self, directory, profile):
        self.profile = profile
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory.chmod(0o700)
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        self.job = {'status': 'idle', 'action': None}

    def start(self, action):
        command_for(action, self.profile)  # validate before allocating a worker
        with self.lock:
            if self.job['status'] == 'running':
                return False
            self.job = {'status': 'running', 'action': action,
                        'started_at': datetime.now(timezone.utc).isoformat()}
        threading.Thread(target=self.run, args=(action,), daemon=True).start()
        return True

    def run(self, action):
        try:
            result = subprocess.run(command_for(action, self.profile), capture_output=True, text=True, timeout=600)
            outcome = {'status': 'passed' if result.returncode == 0 else 'failed',
                       'returncode': result.returncode,
                       'output': (result.stdout + result.stderr)[-12000:]}
        except subprocess.TimeoutExpired as error:
            def text(value):
                return value.decode(errors='replace') if isinstance(value, bytes) else (value or '')
            outcome = {'status': 'failed', 'error': 'TimeoutExpired', 'remote_state': 'unknown',
                       'output': ('SSH timed out; the remote operation may still be running. Check its state before retrying.\n'
                                  + text(error.stdout) + text(error.stderr))[-12000:]}
        except Exception as error:
            outcome = {'status': 'failed', 'error': type(error).__name__}
        with self.lock:
            record = dict(self.job, **outcome, finished_at=datetime.now(timezone.utc).isoformat())
            try:
                descriptor = os.open(self.directory / 'audit.jsonl', os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
                with os.fdopen(descriptor, 'a') as stream:
                    stream.write(json.dumps(record) + '\n')
            except OSError as error:
                record.update(status='audit_failed', audit_error=type(error).__name__)
            self.job = record

    def snapshot(self):
        with self.lock:
            return dict(self.job)


PAGE = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Independent recovery control</title><style>
body{margin:0;background:#f3f6fb;color:#18283e;font:16px/1.65 system-ui,sans-serif}main{max-width:950px;margin:50px auto;padding:24px}h1{font-size:2.3rem;line-height:1.15;letter-spacing:-.04em}.label{color:#315aa0;font-weight:700;font-size:.8rem;letter-spacing:.08em}.card{background:white;padding:28px;border:1px solid #dce3ed;border-radius:18px;margin:20px 0}button{background:#1745a2;color:white;border:0;border-radius:9px;padding:14px 20px;font:600 15px system-ui;cursor:pointer;margin:5px 10px 5px 0}button:disabled{opacity:.5;cursor:wait}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.85rem}a{color:#1745a2}.muted{color:#586b82}#state{font-weight:700}ul{padding-left:22px}</style>
<main><p class="label">OFF-SITE CONTROL · ISOLATED RECOVERY</p><h1>Recover without the production console.</h1>
<p class="muted">This panel runs on your laptop. Commands use your existing SSH access to the independent pentest host.</p>
<section class="card"><h2>Check the recovery environment</h2><p>Check app, database, media, captured email and nginx service health.</p><button data-action="status">Check health</button></section>
<section class="card"><h2>Verify restoration from backup</h2><p>Build a fresh app environment and separate database from the saved offline bundle, verify the app and API, then clean up the temporary instance.</p>
<p class="muted">Prepared-host app + DB test, usually around two minutes. Full media restore, blank-host setup, production parity and traffic promotion are not included in this action.</p>
<button data-action="rehearse">Run app + DB restore test</button></section>
<section class="card"><h2>Latest operation</h2><p id="state">Idle</p><pre id="output">No operation started.</pre></section>
<section class="card"><h2>Readiness deadline: 15 November 2026</h2><p>Production recovery must pass the full functional checklist before it is considered ready. This control is independent of lc-main; production cutover remains a separate action.</p>
<a href="https://pentest.mielenosoitukset.fi/" target="_blank" rel="noopener">Open full test app ↗</a> · <a href="https://pentest.mielenosoitukset.fi/mirror/" target="_blank" rel="noopener">Open static fallback ↗</a></section></main>
<script>const token="TOKEN";let requestError="";const buttons=[...document.querySelectorAll('button[data-action]')];
async function refresh(){const r=await fetch('/state');const j=await r.json();document.querySelector('#state').textContent=(j.action||'No operation')+' — '+j.status;document.querySelector('#output').textContent=requestError||j.output||j.error||j.audit_error||'Waiting for results…';buttons.forEach(b=>b.disabled=j.status==='running');}
buttons.forEach(b=>b.addEventListener('click',async()=>{requestError='';b.disabled=true;const r=await fetch('/run',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({action:b.dataset.action,csrf:token})});if(!r.ok){requestError=(await r.text())+' — reload this page before retrying.';}await refresh();}));setInterval(()=>refresh().catch(()=>{}),2000);refresh();</script></html>'''


def handler_for(recovery):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def valid_host(self):
            return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

        def send(self, code, body, content_type='text/plain; charset=utf-8'):
            body = body.encode()
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.valid_host():
                return self.send(403, 'Invalid host')
            if self.path == '/':
                return self.send(200, PAGE.replace('TOKEN', recovery.token), 'text/html; charset=utf-8')
            if self.path == '/state':
                return self.send(200, json.dumps(recovery.snapshot()), 'application/json')
            self.send(404, 'Not found')

        def do_POST(self):
            if not self.valid_host() or self.headers.get('Origin') != f'http://127.0.0.1:{self.server.server_port}':
                return self.send(403, 'Invalid origin')
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 2048 or self.path != '/run':
                    return self.send(400, 'Invalid request')
                form = parse_qs(self.rfile.read(size).decode(), strict_parsing=True)
                token = form.get('csrf', [''])[0]
                if not hmac.compare_digest(token, recovery.token):
                    return self.send(403, 'Invalid CSRF token')
                accepted = recovery.start(form.get('action', [''])[0])
            except (ValueError, UnicodeDecodeError):
                return self.send(400, 'Invalid action')
            self.send(202 if accepted else 409, 'Started' if accepted else 'Operation already running')
    return Handler


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, default=Path.home() / '.config/mielenosoitukset-dr/control.json')
    args = parser.parse_args()
    recovery = Recovery(Path.home() / '.local/state/mielenosoitukset-dr-control', load_profile(args.profile))
    with ThreadingHTTPServer(('127.0.0.1', PORT), handler_for(recovery)) as server:
        print(f'Independent recovery panel: http://127.0.0.1:{PORT}/', flush=True)
        server.serve_forever()
