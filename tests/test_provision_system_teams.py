import pytest
from scripts.provision_system_teams import provision
from tests.test_system_teams import teams


def test_bootstrap_creates_only_inactive_candidate_and_is_idempotent(app, db, teams):
    for uid, username in ((teams['admin_id'], 'olivia'), (teams['friend_id'], 'tikrutre')):
        db.users.update_one({'_id': uid}, {'$set': {'username': username, 'role': 'global_admin'}})
    db.organizations.update_one({'_id': teams['national']}, {'$set': {'name': 'Valtakunnallinen ylläpitotiimi'}})
    db.organizations.update_one({'_id': teams['board']}, {'$set': {'name': 'Hallitus'}})
    kwargs = dict(national_id=teams['national'], board_id=teams['board'], olivia_id=teams['admin_id'], second_id=teams['friend_id'],
                  username='godolivia', email='god-owner@example.test')
    with app.app_context():
        assert not provision(db, **kwargs)['applied']
        assert db.users.find_one({'username': 'godolivia'}) is None
        first = provision(db, **kwargs, apply=True)
        second = provision(db, **kwargs, apply=True)
        assert first['god_candidate_id'] == second['god_candidate_id']
        assert not first['mail_sent']
        candidate = db.users.find_one({'username': 'godolivia'})
        assert candidate['active'] is False and candidate['confirmed'] is False and candidate['role'] == 'user'
        assert not candidate['global_admin'] and not candidate.get('god_security')
        assert db.email_queue.count_documents({}) == 0
        app.config['BOARD_ORG_ID'] = None
        with pytest.raises(ValueError, match='Configure'):
            provision(db, **kwargs, apply=True)
