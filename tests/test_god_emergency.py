import secrets
from datetime import timedelta, timezone

from bson import ObjectId
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pyotp
import pytest
from werkzeug.security import generate_password_hash

from mielenosoitukset_fi.users import god_auth
from mielenosoitukset_fi.utils.emergency_signatures import PANEL_DOMAIN, public_key_id, sign
from mielenosoitukset_fi.utils.god_emergency import open_request
from mielenosoitukset_fi.utils.time_utils import utcnow
from tests.conftest import _client_for_user, _user_doc
from tests.test_system_teams import teams
from tests.test_god_auth import god


@pytest.fixture
def emergency(app, db, teams):
    panel, usb = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    def pem(key):
        return key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    app.config.update(GOD_EMERGENCY_ENABLED=True, GOD_EMERGENCY_PANEL_KEYS={public_key_id(panel.public_key()): pem(panel)},
                      GOD_EMERGENCY_USB_KEYS={public_key_id(usb.public_key()): pem(usb)})
    candidate = db.users.insert_one({**_user_doc('god-emergency-candidate', 'candidate@example.test', 'test-password-' * 4),
        'active': False, 'confirmed': False, 'god_candidate': True}).inserted_id
    factors = [db.mfas.insert_one({'user_id': candidate, 'secret': pyotp.random_base32()}).inserted_id for _ in range(2)]
    db.user_passkeys.insert_one({'user_id': candidate, 'credential_id': 'ZW1lcmdlbmN5', 'public_key': 'dGVzdA'})
    db.users.update_one({'_id': candidate}, {'$set': {'god_security': {'policy': 1, 'totp_ids': factors,
        'secret_hash': generate_password_hash('separate-test-secret-' * 5)}}})
    now = int(utcnow().replace(tzinfo=timezone.utc).timestamp())
    ticket = sign(panel, {'domain': PANEL_DOMAIN, 'candidate_id': str(candidate), 'launch_id': secrets.token_urlsafe(32),
        'issued_at': now, 'expires_at': now + 300, 'reason': 'Synthetic emergency appointment for regression testing'})
    return {'candidate': candidate, 'ticket': ticket, 'panel': panel, 'usb': usb, **teams}


def api(app, uid, candidate):
    client = _client_for_user(app, uid)
    with client.session_transaction() as state:
        state['governance_csrf_token'] = 'emergency-qa'
    def command(action, **fields):
        return client.post(f'/board/api/clearance/{candidate}', json={'kind': 'god_emergency', 'command': action, **fields},
                           headers={'X-CSRF-Token': 'emergency-qa'})
    return client, command


def test_board_votes_cannot_bypass_normal_god_appointment(app, db, emergency, god):
    _, first = api(app, emergency['admin_id'], emergency['candidate'])
    opened = first('open', ticket=emergency['ticket'])
    assert opened.status_code == 403
    assert db.users.find_one({'_id': emergency['candidate']})['active'] is False
    command, _ = god_client(app, db, god, emergency['candidate'])
    state = command('open', ticket=emergency['ticket']).json['emergency']
    _, second = api(app, emergency['friend_id'], emergency['candidate'])
    assert second('approve_board', request_id=state['id']).status_code == 400
    assert command('status', request_id=state['id']).json['emergency']['approved'] is False
    assert db.users.find_one({'_id': emergency['candidate']})['active'] is False


def god_client(app, db, god, candidate):
    client, command = api(app, god['id'], candidate)
    token = secrets.token_urlsafe(32)
    with app.app_context():
        version = god_auth.credential_version(db, db.users.find_one({'_id': god['id']}))
    db.mfa_login_challenges.insert_one({'_id': god_auth.digest(token), 'kind': 'god_login', 'stage': 'complete', 'user_id': god['id'],
        'version': version, 'completed_at': utcnow(), 'expires_at': utcnow() + timedelta(minutes=30)})
    with client.session_transaction() as state:
        state[god_auth.RECEIPT_KEY] = token
    return command, token


def test_usb_and_fresh_god_need_no_board_votes(app, db, emergency, god):
    command, token = god_client(app, db, god, emergency['candidate'])
    opened = command('open', ticket=emergency['ticket'])
    assert opened.status_code == 200
    state = opened.json['emergency']
    assert not state['board_votes']
    proof = sign(emergency['usb'], state['challenge'])
    assert command('approve_usb_god', request_id=state['id']).status_code == 400
    response = command('approve_usb_god', request_id=state['id'], proof=proof)
    assert response.status_code == 200 and response.json['emergency']['method'] == 'usb_and_god'
    target = db.users.find_one({'_id': emergency['candidate']})
    assert target['active'] and target['role'] == 'god'
    from mielenosoitukset_fi.users.models import User
    with app.app_context():
        assert User.from_OID(target['_id']).has_full_permissions()


def test_usb_without_god_is_not_enough(app, db, emergency, god):
    opened, _ = god_client(app, db, god, emergency['candidate'])
    state = opened('open', ticket=emergency['ticket']).json['emergency']
    proof = sign(emergency['usb'], state['challenge'])
    _, board = api(app, emergency['admin_id'], emergency['candidate'])
    assert board('approve_usb_god', request_id=state['id'], proof=proof).status_code == 403
    assert not db.users.find_one({'_id': emergency['candidate']})['active']


def test_stale_god_login_and_wrong_target_signature_are_rejected(app, db, emergency, god):
    command, token = god_client(app, db, god, emergency['candidate'])
    state = command('open', ticket=emergency['ticket']).json['emergency']
    wrong = sign(emergency['usb'], {**state['challenge'], 'candidate_id': str(ObjectId())})
    assert command('approve_usb_god', request_id=state['id'], proof=wrong).status_code == 400
    db.mfa_login_challenges.update_one({'_id': god_auth.digest(token)}, {'$set': {'completed_at': utcnow() - timedelta(minutes=6)}})
    assert command('approve_usb_god', request_id=state['id'], proof=sign(emergency['usb'], state['challenge'])).status_code == 403


@pytest.mark.parametrize('change', ['expiry', 'credential', 'board_roster'])
def test_changed_or_expired_request_cannot_be_approved(app, db, emergency, god, change):
    command, _ = god_client(app, db, god, emergency['candidate'])
    state = command('open', ticket=emergency['ticket']).json['emergency']
    if change == 'expiry':
        db.board_clearances.update_one({'user_id': str(emergency['candidate'])}, {'$set': {'team_requests.god_emergency.expires_at': utcnow() - timedelta(seconds=1)}})
    elif change == 'credential':
        db.users.update_one({'_id': emergency['candidate']}, {'$set': {'password_hash': generate_password_hash('different-' * 4)}})
    else:
        db.memberships.insert_one({'user_id': emergency['developer_id'], 'organization_id': emergency['board'], 'governance_approved': True})
    assert command('approve_usb_god', request_id=state['id']).status_code == 409


def test_enrollment_panel_signature_and_launch_replay_checks(app, db, emergency, god):
    command, _ = god_client(app, db, god, emergency['candidate'])
    tampered = {**emergency['ticket'], 'message': {**emergency['ticket']['message'], 'reason': 'Tampered emergency reason'}}
    assert command('open', ticket=tampered).status_code == 400
    assert command('open', ticket=emergency['ticket']).status_code == 200
    assert command('open', ticket=emergency['ticket']).status_code == 409
    db.board_clearances.update_one({'user_id': str(emergency['candidate'])}, {'$set': {'team_requests.god_emergency.expires_at': utcnow() - timedelta(seconds=1)}})
    assert command('open', ticket=emergency['ticket']).status_code == 409
    db.users.update_one({'_id': emergency['candidate']}, {'$unset': {'god_security': ''}})
    assert command('open', ticket=emergency['ticket']).status_code == 409
