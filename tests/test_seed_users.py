from werkzeug.security import check_password_hash

from tests._seed_users import _user_template, seed_user_document


def test_seed_users_reuse_real_hashes_without_sharing_mutable_state():
    _user_template.cache_clear()
    first = seed_user_document('Fixture', 'FIXTURE@example.test', 'FixturePass1!', 'Fixture')
    first['_id'] = 'inserted-id'
    first['global_permissions'].append('EDIT_DEMO')
    second = seed_user_document('Fixture', 'FIXTURE@example.test', 'FixturePass1!', 'Fixture')
    assert _user_template.cache_info().misses == 1
    assert _user_template.cache_info().hits == 1
    assert '_id' not in second
    assert second['global_permissions'] == []
    assert second['username'] == 'fixture'
    assert second['email'] == 'fixture@example.test'
    assert check_password_hash(second['password_hash'], 'FixturePass1!')
    assert not check_password_hash(second['password_hash'], 'wrong-password')


def test_seed_users_do_not_reuse_hashes_for_different_passwords():
    first = seed_user_document('Fixture', 'fixture@example.test', 'FirstPass1!', 'Fixture')
    second = seed_user_document('Fixture', 'fixture@example.test', 'SecondPass1!', 'Fixture')
    assert first['password_hash'] != second['password_hash']
    assert not check_password_hash(second['password_hash'], 'FirstPass1!')
    assert check_password_hash(second['password_hash'], 'SecondPass1!')
