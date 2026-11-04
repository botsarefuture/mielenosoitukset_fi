from datetime import timedelta

import pytest
from bson import ObjectId

from mielenosoitukset_fi.users.models import User
from mielenosoitukset_fi.utils.god_appointments import (
    advance_appointment, appointment_approved, appointment_roster, cast_appointment_vote, required_voters,
)
from mielenosoitukset_fi.utils.team_governance import cast_vote
from tests.conftest import _user_doc, _client_for_user
from tests.test_system_teams import teams


@pytest.fixture
def candidate(db, teams):
    return db.users.insert_one({**_user_doc('god-candidate', 'candidate@example.test', 'unusable'),
        'active': False, 'confirmed': False, 'god_candidate': True}).inserted_id


def test_board_round_then_veto_window_then_approval(app, db, teams, candidate, monkeypatch):
    from mielenosoitukset_fi.users import god_auth
    from mielenosoitukset_fi.utils.time_utils import utcnow
    db.users.update_one({'_id': teams['developer_id']}, {'$set': {'global_admin': True}})
    db.users.update_one({'_id': teams['translator_id']}, {'$set': {'role': 'god'}})
    with app.test_request_context():
        roster = appointment_roster(db, candidate)
        assert set(roster['board']) == {str(teams['admin_id']), str(teams['friend_id'])}
        assert str(teams['developer_id']) not in required_voters(roster)
        assert roster['gods'] == [str(teams['translator_id'])]
        assert len(required_voters(roster)) == 3
        for uid in (teams['admin_id'], teams['friend_id']):
            state = cast_appointment_vote(db, candidate, User.from_OID(uid), True)
        assert state['phase'] == 'window' and not state['approved']
        god = User.from_OID(teams['translator_id'])
        monkeypatch.setattr(god_auth, 'valid_god_session', lambda *a, **kw: False)
        with pytest.raises(PermissionError):
            cast_appointment_vote(db, candidate, god, True)
        checked = []
        monkeypatch.setattr(god_auth, 'valid_god_session', lambda *a, **kw: checked.append(kw) or True)
        # A supporting god vote during the window is not a veto and grants nothing.
        assert not cast_appointment_vote(db, candidate, god, True)['approved']
        assert checked == [{'maximum_age': 300}]
        assert not appointment_approved(db, candidate)
        db.board_clearances.update_one({'user_id': str(candidate)},
            {'$set': {'team_requests.god.window_ends_at': utcnow() - timedelta(seconds=1)}})
        assert advance_appointment(db, candidate)['approved']
        assert appointment_approved(db, candidate)
        # No owner security enrollment means no role or active-session grant.
        user = db.users.find_one({'_id': candidate})
        assert not user['active'] and user['role'] == 'user'


def test_roster_change_discards_previous_votes_and_duplicate_votes_do_not_count(app, db, teams, candidate):
    with app.test_request_context():
        first = User.from_OID(teams['admin_id'])
        before = cast_appointment_vote(db, candidate, first, True)
        assert len(cast_appointment_vote(db, candidate, first, True)['votes']) == 1
        db.users.update_one({'_id': teams['developer_id']}, {'$set': {'role': 'god'}})
        after = cast_appointment_vote(db, candidate, User.from_OID(teams['friend_id']), True)
        assert after['id'] != before['id']
        assert set(after['votes']) == {str(teams['friend_id'])}
        assert after['required'] == 2 and not after['approved']


def test_disabling_an_approver_cannot_reduce_god_quorum(app, db, teams, candidate):
    db.users.update_one({'_id': teams['developer_id']}, {'$set': {'role': 'god', 'active': False}})
    with app.test_request_context():
        for uid in (teams['admin_id'], teams['friend_id']):
            state = cast_appointment_vote(db, candidate, User.from_OID(uid), True)
        assert state['required'] == 3 and not state['approved']
        with pytest.raises(PermissionError):
            cast_appointment_vote(db, candidate, User.from_OID(teams['developer_id']), True)


def test_national_approval_or_joint_override_cannot_replace_god_consent(app, db, teams, candidate):
    with app.test_request_context():
        for uid in (teams['admin_id'], teams['friend_id']):
            cast_vote(db, candidate, uid, 'national', True)
        assert not appointment_approved(db, candidate)
    client = _client_for_user(app, teams['admin_id'])
    with client.session_transaction() as state:
        state['governance_csrf_token'] = 'qa'
    response = client.post(f'/board/api/clearance/{candidate}', json={'kind': 'god', 'override': True, 'approved': True},
        headers={'X-CSRF-Token': 'qa'})
    assert response.status_code == 403
    assert db.users.find_one({'_id': candidate})['role'] == 'user'


def test_non_approver_and_candidate_cannot_vote(app, db, teams, candidate):
    with app.test_request_context():
        for uid in (teams['user_id'], candidate):
            with pytest.raises(PermissionError):
                cast_appointment_vote(db, candidate, User.from_OID(uid), True)


def test_first_god_needs_only_the_whole_board(app, db, teams, candidate):
    with app.test_request_context():
        for uid in (teams['admin_id'], teams['friend_id']):
            state = cast_appointment_vote(db, candidate, User.from_OID(uid), True)
        assert state['approved'] and state['method'] == 'unanimous'
        assert state['phase'] == 'collecting' and state['window_ends_at'] is None
        assert appointment_approved(db, candidate)


def test_veto_starts_second_round_with_75_percent_of_combined(app, db, teams, candidate, monkeypatch):
    from mielenosoitukset_fi.users import god_auth
    gods = [db.users.insert_one({**_user_doc(name, f'{name}@example.test', 'unusable-' * 4),
                                 'role': 'god'}).inserted_id for name in ('god-one', 'god-two', 'god-three')]
    monkeypatch.setattr(god_auth, 'valid_god_session', lambda *a, **kw: True)
    with app.test_request_context():
        for uid in (teams['admin_id'], teams['friend_id']):
            state = cast_appointment_vote(db, candidate, User.from_OID(uid), True)
        assert state['phase'] == 'window' and state['required'] == 4 and not state['approved']
        vetoed = cast_appointment_vote(db, candidate, User.from_OID(gods[0]), False)
        assert vetoed['phase'] == 'second_round' and not vetoed['approved']
        assert set(vetoed['votes']) == set()
        assert cast_appointment_vote(db, candidate, User.from_OID(teams['admin_id']), True)['approved'] is False
        cast_appointment_vote(db, candidate, User.from_OID(teams['friend_id']), True)
        assert cast_appointment_vote(db, candidate, User.from_OID(gods[1]), True)['approved'] is False
        final = cast_appointment_vote(db, candidate, User.from_OID(gods[2]), True)
        assert final['approved'] and final['method'] == 'supermajority'
        assert appointment_approved(db, candidate)


def test_clearances_page_renders_the_veto_window(app, db, teams, candidate, monkeypatch):
    from mielenosoitukset_fi.users import god_auth
    db.users.update_one({'_id': teams['translator_id']}, {'$set': {'role': 'god'}})
    monkeypatch.setattr(god_auth, 'valid_god_session', lambda *a, **kw: True)
    with app.test_request_context():
        for uid in (teams['admin_id'], teams['friend_id']):
            cast_appointment_vote(db, candidate, User.from_OID(uid), True)
    body = _client_for_user(app, teams['admin_id']).get('/admin/governance/clearances').get_data(as_text=True)
    assert 'Veto-oikeus päättyy' in body
    # Only the chamber that did not nominate gets the veto control.
    god_body = _client_for_user(app, teams['translator_id']).get('/admin/governance/clearances').get_data(as_text=True)
    assert 'Käytä veto-oikeutta' in god_body
