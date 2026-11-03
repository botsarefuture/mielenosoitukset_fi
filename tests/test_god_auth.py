"""God authentication cannot fall through the existing single-factor flows."""
import re
from datetime import timedelta
from types import SimpleNamespace

import pyotp
import pytest
from bson import ObjectId
from werkzeug.security import generate_password_hash
from mielenosoitukset_fi.users import god_auth
from mielenosoitukset_fi.utils.team_governance import cast_vote
from mielenosoitukset_fi.utils.time_utils import utcnow
from tests.conftest import _client_for_user
from tests.test_system_teams import teams

PASSWORD = 'main-password-for-god-tests-only-' * 2
SECRET = 'separate-recovery-secret-for-tests-only-' * 2
ORIGIN = 'https://mielenosoitukset.fi'


@pytest.fixture
def god(app, db, teams):
    target = teams['user_id']
    factors = [ObjectId(), ObjectId()]
    secrets = [pyotp.random_base32(), pyotp.random_base32()]
    for oid, value in zip(factors, secrets):
        db.mfas.insert_one({'_id': oid, 'user_id': target, 'secret': value})
    db.user_passkeys.insert_one({'user_id': target, 'credential_id': 'dGVzdA', 'public_key': 'dGVzdA'})
    db.users.update_one({'_id': target}, {'$set': {'password_hash': generate_password_hash(PASSWORD), 'role': 'god',
        'governance_managed': True, 'god_security': {'policy': 1, 'totp_ids': factors, 'secret_hash': generate_password_hash(SECRET)}}})
    with app.app_context():
        for voter in (teams['admin_id'], teams['friend_id']):
            cast_vote(db, target, voter, 'national', True)
    return {**teams, 'secrets': secrets, 'id': target}


def api(client):
    status = client.post('/users/auth/login', json={'god_action': 'status'}, headers={'Origin': ORIGIN})
    assert status.status_code == 200
    csrf = status.json['csrf']
    def action(name, **fields):
        return client.post('/users/auth/login', json={'god_action': name, **fields}, headers={'Origin': ORIGIN, 'X-CSRF-Token': csrf})
    return action


def test_god_cannot_use_password_or_existing_session_cookie(app, db, god):
    client = app.test_client()
    response = client.post('/users/auth/login', data={'username': 'alice', 'password': PASSWORD})
    assert response.status_code == 302 and response.location == '/auth/god'
    assert _client_for_user(app, god['id']).get('/admin/governance/').status_code == 302
    with client.session_transaction() as state:
        assert '_user_id' not in state


def test_every_factor_required_before_login_and_receipt_revokes_on_credential_change(app, db, god, monkeypatch):
    client = app.test_client()
    action = api(client)
    assert action('start', username='alice', password=PASSWORD).json['stage'] == 'totp_first'
    assert action('final_secret', secret=SECRET).status_code == 403
    assert action('totp_first', code=pyotp.TOTP(god['secrets'][0]).now()).json['stage'] == 'email_code'
    code = re.search(r'\d{6}', db.email_queue.find_one({'subject': 'God-tilin kirjautumisen vahvistus'})['body']).group()
    assert action('email_code', code=code).json['stage'] == 'passkey'
    calls = []
    def verify(credential, user_id, **kwargs):
        calls.append((user_id, kwargs))
        return {'user_id': user_id}, None
    monkeypatch.setattr(god_auth.webauthn, 'verify_authentication', verify)
    assert action('passkey', credential={}).json['stage'] == 'totp_second'
    assert calls == [(god['id'], {'purpose': 'god_login', 'require_user_verification': True})]
    assert action('totp_second', code=pyotp.TOTP(god['secrets'][1]).now()).json['stage'] == 'email_link'
    link = list(db.email_queue.find({'subject': 'God-tilin kirjautumisen vahvistus'}))[-1]['body']
    token = re.search(r'#verify=(\S+)', link).group(1)
    with client.session_transaction() as state:
        assert '_user_id' not in state
    assert action('email_link', token=token).json['stage'] == 'final_secret'
    assert action('final_secret', secret=SECRET).json['stage'] == 'complete'
    assert client.get('/admin/governance/').status_code == 200
    db.users.update_one({'_id': god['id']}, {'$set': {'password_hash': generate_password_hash('changed')}})
    assert client.get('/admin/governance/').status_code == 302


def test_failed_stage_locks_after_five_attempts_and_expiry_is_enforced(app, db, god):
    client = app.test_client()
    action = api(client)
    action('start', username='alice', password=PASSWORD)
    for _ in range(5):
        assert action('totp_first', code='bad').status_code == 403
    assert action('totp_first', code=pyotp.TOTP(god['secrets'][0]).now()).status_code == 403
    assert action('start', username='alice', password=PASSWORD).status_code == 200
    db.mfa_login_challenges.update_many({'kind': 'god_login'}, {'$set': {'expires_at': utcnow() - timedelta(seconds=1)}})
    assert action('totp_first', code=pyotp.TOTP(god['secrets'][0]).now()).status_code == 403


def test_totp_replay_and_duplicate_authenticator_secret_are_rejected(app, db, god):
    with app.test_request_context():
        user = db.users.find_one({'_id': god['id']})
        factor = god_auth._factors(db, user)[0]
        code = pyotp.TOTP(factor['secret']).now()
        assert god_auth._consume_totp(db, factor, code)
        assert not god_auth._consume_totp(db, factor, code)
        second = user['god_security']['totp_ids'][1]
        db.mfas.update_one({'_id': second}, {'$set': {'secret': factor['secret']}})
        assert god_auth.credential_version(db, user) is None


def test_csrf_origin_and_short_password_are_rejected(app, db, god):
    client = app.test_client()
    assert client.post('/users/auth/login', json={'god_action': 'status'}, headers={'Origin': 'https://attacker.example'}).status_code == 403
    action = api(client)
    assert client.post('/users/auth/login', json={'god_action': 'start'}, headers={'Origin': ORIGIN}).status_code == 403
    assert action('start', username='alice', password='short').status_code == 403


def test_ordinary_passkey_login_does_not_issue_god_cookie(app, db, god, monkeypatch):
    from mielenosoitukset_fi.users.BPs import passkeys
    monkeypatch.setattr(passkeys.webauthn, 'verify_authentication', lambda *a, **kw: ({'user_id': god['id']}, None))
    client = app.test_client()
    response = client.post('/users/auth/api/v2/passkeys/login/verify', json={'credential': {'test': True}})
    assert response.status_code == 403 and response.json['redirect'] == '/auth/god'
    with client.session_transaction() as state:
        assert '_user_id' not in state


def test_owner_enrollment_stays_inactive_until_both_board_votes(app, db, teams, monkeypatch):
    from tests.conftest import _user_doc
    candidate = db.users.insert_one({**_user_doc('godolivia', 'god@example.test', 'not-a-login'),
        'active': False, 'confirmed': False, 'god_candidate': True}).inserted_id
    owner_secret = pyotp.random_base32()
    db.mfas.insert_one({'user_id': teams['admin_id'], 'secret': owner_secret})
    client = _client_for_user(app, teams['admin_id'])
    action = api(client)
    assert action('enroll_start', password='AdminPass1!', code=pyotp.TOTP(owner_secret).now()).json['stage'] == 'enroll_email'
    body = db.email_queue.find_one({'subject': 'God-tilin kirjautumisen vahvistus'})['body']
    token = re.search(r'#enroll=(\S+)', body).group(1)
    response = action('enroll_email', token=token)
    assert response.json['stage'] == 'enroll_passkey' and len(response.json['authenticators']) == 2
    verified = SimpleNamespace(credential_id=b'god-enrollment', credential_public_key=b'public-key', sign_count=0)
    monkeypatch.setattr(god_auth.webauthn, 'verify_registration', lambda *a, **kw: (verified, None))
    assert action('enroll_passkey_verify', credential={}).json['stage'] == 'enroll_secrets'
    proof = db.mfa_login_challenges.find_one({'kind': 'god_enrollment', 'user_id': candidate})
    codes = [pyotp.TOTP(secret).now() for secret in proof['totp_secrets']]
    assert action('enroll_secrets', password=PASSWORD, secret=PASSWORD, codes=codes).status_code == 403
    response = action('enroll_secrets', password=PASSWORD, secret=SECRET, codes=codes)
    assert response.json == {'stage': 'enrolled', 'activated': False}
    assert db.users.find_one({'_id': candidate})['active'] is False
    with app.app_context():
        assert not cast_vote(db, candidate, teams['admin_id'], 'national', True)['approved']
        assert db.users.find_one({'_id': candidate})['active'] is False
        assert cast_vote(db, candidate, teams['friend_id'], 'national', True)['approved']
    user = db.users.find_one({'_id': candidate})
    assert user['active'] and user['confirmed'] and user['role'] == 'god'
    with client.session_transaction() as state:
        assert state['_user_id'] == str(teams['admin_id'])
        assert god_auth.RECEIPT_KEY not in state
    assert action('enroll_start', password='AdminPass1!', code=pyotp.TOTP(owner_secret).now()).status_code == 403


def test_joint_override_requires_two_distinct_accounts_and_fresh_god_receipt(app, db, god):
    from mielenosoitukset_fi.utils.team_governance import cast_joint_override
    from mielenosoitukset_fi.users.models import User
    target = god['developer_id']
    with app.test_request_context():
        assert not cast_joint_override(db, target, User.from_OID(god['admin_id']), 'national')['approved']
        token = 'synthetic-test-receipt'
        user = db.users.find_one({'_id': god['id']})
        db.mfa_login_challenges.insert_one({'_id': god_auth.digest(token), 'kind': 'god_login', 'user_id': god['id'], 'stage': 'complete',
            'expires_at': utcnow() + timedelta(minutes=30), 'completed_at': utcnow() - timedelta(minutes=6), 'version': god_auth.credential_version(db, user)})
        from flask import session
        session[god_auth.RECEIPT_KEY] = token
        with pytest.raises(PermissionError):
            cast_joint_override(db, target, User.from_OID(god['id']), 'national')
        db.mfa_login_challenges.update_one({'_id': god_auth.digest(token)}, {'$set': {'completed_at': utcnow()}})
        assert cast_joint_override(db, target, User.from_OID(god['id']), 'national')['approved']


def test_god_cannot_create_or_reuse_bearer_token_or_reuse_main_secret(app, db, god):
    from mielenosoitukset_fi.utils.tokens import create_token, check_token
    from mielenosoitukset_fi.api.exceptions import ApiException
    from mielenosoitukset_fi.users.models import User
    with app.test_request_context():
        with pytest.raises(ValueError):
            create_token(user_id=god['id'])
        db.api_tokens.insert_one({'user_id': god['id'], 'token': god_auth.digest('old-token'), 'expires_at': utcnow() + timedelta(days=1)})
        with pytest.raises(ApiException):
            check_token('old-token')
        with pytest.raises(ValueError):
            User.from_OID(god['id'])._change_password(SECRET)
