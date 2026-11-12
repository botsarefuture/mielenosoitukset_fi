from datetime import timedelta

import pytest
from bson import ObjectId
from werkzeug.security import generate_password_hash

from mielenosoitukset_fi.users.models import User
from mielenosoitukset_fi.utils.security_cases import decide, open_case, process_cases, reconcile_case
from mielenosoitukset_fi.utils.team_governance import GovernanceConflict
from mielenosoitukset_fi.utils.time_utils import utcnow
from tests.conftest import _client_for_user
from tests.test_system_teams import teams

REASON = 'Suspicious account activity needs immediate investigation'
HEARING = 'Owner contacted and heard; recovery performed by the owner'


def approve(db, case, uid, action='suspend', **kwargs):
    return decide(db, case['_id'], User.from_OID(uid), action, REASON, **kwargs)


def test_distinct_board_votes_suspend_and_revoke_without_homelab(app, db, teams):
    target = teams['user_id']
    client = _client_for_user(app, target)
    db.api_tokens.insert_one({'user_id': target, 'token': 'synthetic'})
    db.magic_links.insert_one({'intended_recipient': {'user_id': str(target)}})
    with app.test_request_context():
        case = open_case(db, User.from_OID(teams['admin_id']), target, REASON)
        assert case['status'] == 'pending'
        assert approve(db, case, teams['admin_id'])['status'] == 'pending'
        case = approve(db, case, teams['friend_id'])
        assert case['status'] == 'suspended'
        assert not User.from_OID(target).is_active
        assert db.api_tokens.find_one({'user_id': target})['revoked_at']
        assert db.magic_links.find_one({'intended_recipient.user_id': str(target)})['revoked'] is True
    assert client.get('/users/auth/profile').status_code != 200


def test_deadline_escalates_once_and_never_auto_unbans(app, db, teams):
    with app.test_request_context():
        case = open_case(db, User.from_OID(teams['admin_id']), teams['user_id'], REASON)
        approve(db, case, teams['friend_id'])
        db.security_cases.update_one({'_id': case['_id']}, {'$set': {'review_due_at': utcnow() - timedelta(days=1)}})
        process_cases(db)
        count = db.email_queue.count_documents({})
        process_cases(db)
        assert db.email_queue.count_documents({}) == count
        assert sum(e['action'] == 'overdue' for e in db.security_cases.find_one()['events']) == 1
        assert not User.from_OID(teams['user_id']).is_active


def test_restore_requires_two_votes_hearing_and_changed_credentials_and_old_cookie_stays_revoked(app, db, teams):
    target = teams['user_id']
    old_client = _client_for_user(app, target)
    with app.test_request_context():
        case = open_case(db, User.from_OID(teams['admin_id']), target, REASON)
        case = approve(db, case, teams['friend_id'])
        with pytest.raises(GovernanceConflict):
            approve(db, case, teams['admin_id'], 'restore', hearing=HEARING, recovery_confirmed=True)
        db.users.update_one({'_id': target}, {'$set': {'password_hash': generate_password_hash('owner-changed-credentials')}})
        assert approve(db, case, teams['admin_id'], 'restore', hearing=HEARING, recovery_confirmed=True)['status'] == 'suspended'
        restored = approve(db, case, teams['friend_id'], 'restore', hearing=HEARING, recovery_confirmed=True)
        assert restored['status'] == 'restored'
        assert User.from_OID(target).is_active
        # A delayed worker holding the old suspension snapshot cannot re-freeze.
        old = {**case, 'effect_pending': case['events'][-1]}
        reconcile_case(db, old)
        assert User.from_OID(target).is_active
    assert old_client.get('/api/session').json['authenticated'] is False


def test_affected_board_person_cannot_vote_via_separate_god_account_and_quorum_stays_missing(app, db, teams, monkeypatch):
    from mielenosoitukset_fi.utils import security_cases
    target = teams['admin_id']
    operator = teams['developer_id']
    db.users.update_one({'_id': operator}, {'$set': {'role': 'god', 'god_security.owner_id': str(teams['friend_id'])}})
    monkeypatch.setattr(security_cases, '_fresh_god', lambda *a: True)
    with app.test_request_context():
        case = open_case(db, User.from_OID(operator), target, REASON)
        assert case['status'] == 'suspended'
        assert approve(db, case, teams['friend_id'], 'remove_role', hearing=HEARING)['status'] == 'suspended'
        assert db.security_cases.find_one()['proposal']['required'] == 2
        db.users.update_one({'_id': target}, {'$set': {'security_suspension.active': False}})
        with pytest.raises(PermissionError):
            approve(db, case, target, 'remove_role', hearing=HEARING)


def test_removal_needs_majority_and_preserves_membership_history(app, db, teams):
    target = teams['developer_id']
    db.memberships.insert_one({'user_id': target, 'organization_id': teams['board'], 'governance_approved': True})
    for _ in range(3):
        suffix = ObjectId()
        uid = db.users.insert_one({**db.users.find_one({'_id': teams['friend_id']}), '_id': suffix,
                                   'username': f'board-{suffix}', 'username_canonical': f'board-{suffix}',
                                   'email': f'board-{suffix}@example.test',
                                   'email_canonical': f'board-{suffix}@example.test'}).inserted_id
        db.memberships.insert_one({'user_id': uid, 'organization_id': teams['board'], 'governance_approved': True})
    with app.test_request_context():
        case = open_case(db, User.from_OID(teams['admin_id']), target, REASON)
        case = approve(db, case, teams['friend_id'])
        case = approve(db, case, teams['admin_id'], 'remove_role', hearing=HEARING)
        case = approve(db, case, teams['friend_id'], 'remove_role', hearing=HEARING)
        assert case['status'] == 'suspended' and case['proposal']['required'] == 3
        third = db.memberships.find_one({'organization_id': teams['board'], 'user_id': {'$nin': [target, teams['admin_id'], teams['friend_id']]}})['user_id']
        assert approve(db, case, third, 'remove_role', hearing=HEARING)['status'] == 'role_removed'
        assert db.memberships.find_one({'user_id': target})['governance_approved'] is False


def test_lockdown_requires_votes_and_preserves_auth_and_admin(app, db, teams):
    with app.test_request_context():
        case = open_case(db, User.from_OID(teams['admin_id']), None, REASON, lockdown=True)
        assert not db.panic.find_one({'panic': True})
        approve(db, case, teams['friend_id'], 'lockdown')
    client = _client_for_user(app, teams['admin_id'])
    assert client.get('/').status_code == 503
    assert client.get('/users/auth/login').status_code != 503
    assert client.get('/admin/governance/security').status_code == 200
    with app.test_request_context():
        approve(db, case, teams['admin_id'], 'reopen')
        approve(db, case, teams['friend_id'], 'reopen')
    assert not db.panic.find_one({'panic': True})


def test_ordinary_admin_cannot_use_security_page_and_csrf_is_required(app, db, teams):
    client = _client_for_user(app, teams['developer_id'])
    assert client.get('/admin/governance/security').status_code == 403
    client = _client_for_user(app, teams['admin_id'])
    assert client.post('/admin/governance/security', data={'action': 'lockdown', 'reason': REASON}).status_code == 403
