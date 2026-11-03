"""Small homelab-panel extension. It signs launches, never approvals/logins."""
import hmac
import html
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import secrets
import time
from urllib.parse import parse_qs

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
try:
    from moso_emergency_signatures import PANEL_DOMAIN, encode, canonical, public_key_id, sign
except ModuleNotFoundError:
    from mielenosoitukset_fi.utils.emergency_signatures import PANEL_DOMAIN, encode, canonical, public_key_id, sign

CONFIG = Path(os.environ.get('MOSO_PANEL_CONFIG', '/etc/moso-emergency-panel/config.json'))
COOKIE = 'moso_emergency_csrf'


def _config():
    return json.loads(CONFIG.read_text())


def _redirect(handler, location):
    handler.send_response(303)
    handler.send_header('Location', location)
    handler.send_header('Cache-Control', 'no-store')
    handler.end_headers()


def handle(handler, authed=False):
    if handler.path.split('?', 1)[0] != '/moso-emergency':
        handler.send_error(404)
        return
    if not authed:
        # The LAN page is reachable only after the panel passphrase is unlocked.
        _redirect(handler, '/logins')
        return
    config = _config()
    token = secrets.token_urlsafe(32)
    message = ''
    if handler.command == 'POST':
        try:
            length = int(handler.headers.get('Content-Length', '0'))
            if not 0 < length <= 16384 or handler.headers.get('Origin') not in config['origins']:
                raise ValueError('Invalid request origin or size')
            fields = parse_qs(handler.rfile.read(length).decode('utf-8'), max_num_fields=4)
            cookies = SimpleCookie(handler.headers.get('Cookie', ''))
            cookie = cookies.get(COOKIE)
            submitted = fields.get('csrf', [''])[0]
            if not cookie or not submitted.isascii() or not hmac.compare_digest(cookie.value, submitted):
                raise ValueError('Session validation failed; reload the page')
            if config.get('enabled') is not True:
                raise ValueError('Production activation is pending')
            candidate = fields.get('candidate_id', [''])[0].lower()
            reason = fields.get('reason', [''])[0].strip()
            if len(candidate) != 24 or any(c not in '0123456789abcdef' for c in candidate) or not 10 <= len(reason) <= 1000:
                raise ValueError('Supply the account ID and a reason of 10–1000 characters')
            key = serialization.load_pem_private_key(Path(config['private_key']).read_bytes(), password=None)
            now = int(time.time())
            ticket = sign(key, {'domain': PANEL_DOMAIN, 'candidate_id': candidate, 'reason': reason,
                'launch_id': secrets.token_urlsafe(32), 'issued_at': now, 'expires_at': now + 300})
            base = config.get('admin_base', 'https://mielenosoitukset.fi').rstrip('/')
            _redirect(handler, base + '/admin/governance/clearances#emergency=' + encode(canonical(ticket)))
            return
        except (ValueError, KeyError, UnicodeError):
            message = 'Request could not be opened. Reload the page, check the fields and try again.'
    disabled = '' if config.get('enabled') is True else 'disabled'
    status = 'Ready to open a request in the HTTPS administration service.' if not disabled else 'Waiting for the protected application deployment and public-key registration. Approval is disabled.'
    body = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>God emergency appointment | homelab</title>
<style>:root{{color-scheme:dark}}*{{box-sizing:border-box}}body{{background:#0f1115;color:#e6e9ef;font:14px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace;margin:0;padding:20px}}main{{max-width:700px;margin:auto}}section{{background:#181b22;border:1px solid #323a48;border-radius:9px;padding:20px}}h1{{font-size:22px;line-height:1.4}}a{{color:#8bbaff}}label{{display:block;margin:20px 0 6px}}input,textarea,button{{width:100%;font:inherit;min-height:48px;padding:12px;border:1px solid #596579;border-radius:5px;background:#0f1115;color:#e6e9ef}}button{{margin-top:20px;background:#285c9c;font-weight:bold;cursor:pointer}}button:disabled{{opacity:.55;cursor:default}}:focus-visible{{outline:3px solid #8bbaff;outline-offset:3px}}.status{{color:#c8d0df}}.error{{border-left:4px solid #ffb020;padding-left:12px}}</style></head><body><main><p><a href="/">← homelab status</a></p><section>
<h1>God emergency appointment</h1><p>This opens a named request in Mielenosoitukset.fi administration. It grants no access by itself.</p>
<p>Emergency approval requires either <strong>two distinct board members</strong>, or <strong>a USB signature and a fresh complete god login</strong>. The nominee must complete security enrollment in both cases.</p>
<p class="status">{html.escape(status)}</p>{'<p class="error" role="alert">'+html.escape(message)+'</p>' if message else ''}
<form method="post"><input type="hidden" name="csrf" value="{token}"><label for="candidate">Target account ID</label><input id="candidate" name="candidate_id" required pattern="[a-fA-F0-9]{{24}}" value="{html.escape(config.get('candidate_id',''),quote=True)}" autocomplete="off">
<label for="reason">Emergency reason</label><textarea id="reason" name="reason" rows="5" required minlength="10" maxlength="1000"></textarea>
<button type="submit" {disabled}>Open request in secure administration</button></form><p>Passwords, authenticator codes and private USB keys are never entered on this LAN page.</p></section></main></body></html>'''.encode()
    handler.send_response(200)
    handler.send_header('Content-Type', 'text/html; charset=utf-8')
    handler.send_header('Cache-Control', 'no-store')
    handler.send_header('Referrer-Policy', 'no-referrer')
    handler.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
    handler.send_header('Set-Cookie', f'{COOKIE}={token}; Path=/moso-emergency; HttpOnly; SameSite=Strict; Max-Age=300')
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def initialize(directory):
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = directory / 'private.pem'
    key = Ed25519PrivateKey.generate()
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, 'wb') as target:
        target.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return {'key_id': public_key_id(key.public_key()), 'public_key': key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode('ascii')}


if __name__ == '__main__':
    print(json.dumps(initialize(Path('/etc/moso-emergency-panel')), indent=2))
