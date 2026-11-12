"""Quorum and bypass regressions for protected administration organizations."""
import pytest
from bson import ObjectId
from mielenosoitukset_fi.users.models import User
from mielenosoitukset_fi.utils.system_teams import user_team_access, national_recipients
from mielenosoitukset_fi.utils.team_governance import cast_vote, cast_joint_override, GovernanceConflict
from tests.conftest import _client_for_user


@pytest.fixture
def teams(app, db, seeded_data):
    national, board = ObjectId(), ObjectId()
    app.config.update(NATIONAL_ADMIN_ORG_ID=str(national), BOARD_ORG_ID=str(board), OVERRIDE_OLIVIA_USER_ID=str(seeded_data['admin_id']))
    db.organizations.insert_many([{'_id': national, 'name': 'National QA', 'description': '', 'email': '', 'verified': True}, {'_id': board, 'name': 'Board QA', 'description': '', 'email': '', 'verified': True}])
    for user_id in [seeded_data['admin_id'], seeded_data['friend_id']]:
        db.memberships.insert_one({'user_id': user_id, 'organization_id': board, 'role': 'member', 'permissions': [],
                                   'governance_approved': True, 'grant_source': 'maintainer_bootstrap'})
    return {'national': national, 'board': board, **seeded_data}


def test_two_distinct_votes_grant_live_access_and_withdrawal_revokes(app, db, teams):
    with app.app_context():
        target, first, second = teams['user_id'], teams['admin_id'], teams['friend_id']
        assert not cast_vote(db, target, first, 'national', True)['approved']
        assert not cast_vote(db, target, first, 'national', True)['approved']
        assert not user_team_access(db, target)
        assert cast_vote(db, target, second, 'national', True)['approved']
        user = User.from_OID(target)
        assert user.global_admin and user.has_full_permissions()
        user.displayname = 'Profile edit'
        user.save()
        assert db.users.find_one({'_id': target})['global_admin'] is False
        assert not cast_vote(db, target, first, 'national', False)['approved']
        assert not User.from_OID(target).global_admin


def test_board_admission_is_unanimous_and_roster_cannot_shrink(app, db, teams):
    with app.app_context():
        target, first, second = teams['user_id'], teams['admin_id'], teams['friend_id']
        assert not cast_vote(db, target, first, 'board', True)['approved']
        db.memberships.delete_one({'user_id': second, 'organization_id': teams['board']})
        with pytest.raises(GovernanceConflict):
            cast_vote(db, target, first, 'board', True)
        db.memberships.insert_one({'user_id': second, 'organization_id': teams['board'], 'governance_approved': True})
        assert cast_vote(db, target, second, 'board', True)['approved']
        with pytest.raises(PermissionError):
            cast_vote(db, target, target, 'national', True)


def test_ordinary_membership_and_org_edits_cannot_modify_protected_teams(app, db, teams):
    from mielenosoitukset_fi.utils.classes.MemberShip import MemberShip
    from mielenosoitukset_fi.utils.classes.Organization import Organization
    with app.app_context():
        assert not User.from_OID(teams['admin_id']).has_permission('EDIT_ORGANIZATION', teams['board'])
        row = db.memberships.find_one({'organization_id': teams['board']})
        with pytest.raises(PermissionError):
            MemberShip.from_dict(row).save()
        org = Organization.from_dict(db.organizations.find_one({'_id': teams['board']}))
        with pytest.raises(PermissionError):
            org.save()


def test_only_actual_board_members_can_vote_even_with_old_global_permission(app, db, teams):
    outsider = teams['developer_id']
    db.users.update_one({'_id': outsider}, {'$set': {'global_permissions': ['MANAGE_CLEARANCE'], 'global_admin': True}})
    client = _client_for_user(app, outsider)
    with client.session_transaction() as state:
        state['governance_csrf_token'] = 'test'
    response = client.post(f"/board/api/clearance/{teams['user_id']}", json={'approved': True}, headers={'X-CSRF-Token': 'test'})
    assert response.status_code == 403


def test_national_mail_uses_eligible_members_and_fails_closed_if_empty(app, db, teams):
    with app.app_context():
        with pytest.raises(RuntimeError):
            national_recipients(db)
        for voter in (teams['admin_id'], teams['friend_id']):
            cast_vote(db, teams['user_id'], voter, 'national', True)
        recipients = national_recipients(db)
        assert recipients == [{'user_id': str(teams['user_id']), 'username': 'alice', 'email': 'alice@example.test'}]
        db.users.update_one({'_id': teams['user_id']}, {'$set': {'banned': True}})
        with pytest.raises(RuntimeError):
            national_recipients(db)


def test_one_override_account_cannot_grant_access(app, db, teams):
    with app.test_request_context():
        user = User.from_OID(teams['admin_id'])
        first = cast_joint_override(db, teams['user_id'], user, 'national')
        assert not first['approved']
        assert not user_team_access(db, teams['user_id'])
        assert not cast_joint_override(db, teams['user_id'], user, 'national')['approved']


def test_user_save_cannot_promote_without_membership_and_quorum(app, db, teams):
    with app.app_context():
        user = User.from_OID(teams['user_id'])
        user.role = 'global_admin'
        with pytest.raises(PermissionError):
            user.save()


def test_disabling_board_login_cannot_shrink_unanimous_quorum(app, db, teams):
    with app.app_context():
        target, first, second = teams['user_id'], teams['admin_id'], teams['friend_id']
        db.users.update_one({'_id': second}, {'$set': {'active': False}})
        result = cast_vote(db, target, first, 'board', True)
        assert result['required'] == 2 and not result['approved']
        with pytest.raises(PermissionError):
            cast_vote(db, target, second, 'board', True)
