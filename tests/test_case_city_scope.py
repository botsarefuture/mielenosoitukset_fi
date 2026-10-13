"""Case reads and mutations must share an explicit permission/city boundary."""

from copy import deepcopy
import pytest
import re
from bson import ObjectId
from mielenosoitukset_fi.users.models import User
from tests.conftest import _client_for_user
from tests.test_city_scoped_admin import _create_scoped_admin


def _city_cases(app, db, seeded_data, permissions=None):
    actor = _create_scoped_admin(
        db, ["helsinki"], permissions or ["LIST_CASES", "VIEW_CASE", "EDIT_CASE"],
    )
    target = seeded_data["case_id"]
    db.cases.update_one({"_id": target}, {"$set": {"demo_id": seeded_data["pending_demo_id"]}})
    foreign_demo = deepcopy(db.demonstrations.find_one({"_id": seeded_data["pending_demo_id"]}))
    foreign_demo.update({"_id": ObjectId(), "city": "Turku", "city_key": "turku", "title": "Foreign scope demo"})
    db.demonstrations.insert_one(foreign_demo)
    foreign_case = deepcopy(db.cases.find_one({"_id": target}))
    foreign_case.update({"_id": ObjectId(), "demo_id": foreign_demo["_id"], "running_num": 888888})
    db.cases.insert_one(foreign_case)
    return _client_for_user(app, actor), actor, target, foreign_case["_id"], foreign_demo["_id"]


def test_ordinary_user_cannot_read_cases(user_client, seeded_data):
    assert user_client.get("/admin/case/").status_code == 403
    assert user_client.get(f"/admin/case/{seeded_data['case_id']}/").status_code == 403


def test_every_case_route_declares_its_permission(app):
    from mielenosoitukset_fi.utils.case_access import CASE_PERMISSIONS
    for rule in app.url_map.iter_rules():
        if rule.endpoint.startswith('admin_case.'):
            declaration = getattr(app.view_functions[rule.endpoint], 'case_permissions', None)
            assert declaration, rule.endpoint
            assert set(declaration.values() if isinstance(declaration, dict) else [declaration]) <= CASE_PERMISSIONS


def test_undeclared_case_route_fails_closed(app, admin_client):
    app.add_url_rule('/admin/case/undeclared-check/', endpoint='admin_case.undeclared_check', view_func=lambda: 'not allowed')
    assert admin_client.get('/admin/case/undeclared-check/').status_code == 403


def test_case_list_reuses_edit_scope_and_preserves_autoclose(app, db, seeded_data, monkeypatch):
    from inspect import unwrap
    route_globals = unwrap(app.view_functions['admin_case.cases']).__globals__
    client, _actor, own, foreign, _demo = _city_cases(app, db, seeded_data)
    original = db.cases.find_one({'_id': own})
    additional = [dict(deepcopy(original), _id=ObjectId(), running_num=900000 + index) for index in range(6)]
    db.cases.insert_many(additional)
    db.demonstrations.update_one({'_id': seeded_data['pending_demo_id']}, {'$set': {'approved': True}})
    calls = []
    scope_query = route_globals['case_scope_query']
    def counted(user, permission):
        calls.append(permission)
        return scope_query(user, permission)
    monkeypatch.setitem(route_globals, 'case_scope_query', counted)
    assert client.get('/admin/case/').status_code == 200
    assert calls.count('EDIT_CASE') == 1
    for case_id in [own, *[case['_id'] for case in additional]]:
        assert db.cases.find_one({'_id': case_id})['meta']['closed'] is True
    assert not (db.cases.find_one({'_id': foreign}).get('meta') or {}).get('closed')


def test_city_case_list_and_detail_use_same_scope(app, db, seeded_data):
    client, actor, own, foreign, _demo = _city_cases(app, db, seeded_data)
    assert User.from_db(db.users.find_one({"_id": actor})).has_permission("LIST_CASES")
    response = client.get("/admin/case/")
    assert response.status_code == 200
    assert "Foreign scope demo" not in response.get_data(as_text=True)
    assert "Pending Demonstration" in response.get_data(as_text=True)
    assert client.get(f"/admin/case/{own}/").status_code == 200
    assert client.get(f"/admin/case/{foreign}/").status_code == 403


@pytest.mark.parametrize("action,data", [
    ("add_action/", {"action_type": "note", "reason": "Scoped note"}),
    ("close/", {"reason": "Scoped close"}),
    ("reopen/", {"reason": "Scoped reopen"}),
])
def test_city_case_mutations_reject_foreign_targets(app, db, seeded_data, action, data):
    client, _actor, _own, foreign, _demo = _city_cases(app, db, seeded_data)
    before = db.cases.find_one({"_id": foreign})
    response = client.post(f"/admin/case/{foreign}/{action}", json=data, data=None)
    assert response.status_code == 403
    assert db.cases.find_one({"_id": foreign}) == before


def test_city_admin_can_add_note_to_own_case(app, db, seeded_data):
    client, _actor, own, _foreign, _demo = _city_cases(app, db, seeded_data)
    response = client.post(f"/admin/case/{own}/add_action/", data={
        "action_type": "note", "reason": "Scoped note",
    })
    assert response.status_code == 302
    assert "Scoped note" in repr(db.cases.find_one({"_id": own})["action_logs"])


def test_case_relink_cannot_cross_city_boundary(app, db, seeded_data):
    client, _actor, own, _foreign, demo = _city_cases(app, db, seeded_data)
    before = db.cases.find_one({"_id": own})["demo_id"]
    response = client.post(f"/admin/case/{own}/link_demo/", data={"demo_id": str(demo)})
    assert response.status_code == 403
    assert db.cases.find_one({"_id": own})["demo_id"] == before


def test_revoked_case_grant_loses_access(app, db, seeded_data):
    client, actor, own, _foreign, _demo = _city_cases(app, db, seeded_data)
    db.admin_scope_grants.update_many({"user_id": actor}, {"$set": {"revoked_at": "revoked"}})
    assert client.get("/admin/case/").status_code == 403
    assert client.get(f"/admin/case/{own}/").status_code == 403


def test_view_only_case_grant_cannot_write_or_autoclose(app, db, seeded_data):
    client, _actor, own, _foreign, _demo = _city_cases(
        app, db, seeded_data, ["LIST_CASES", "VIEW_CASE"],
    )
    db.demonstrations.update_one({"_id": seeded_data["pending_demo_id"]}, {"$set": {"approved": True}})
    before = db.cases.find_one({"_id": own})
    assert client.get("/admin/case/").status_code == 200
    assert db.cases.find_one({"_id": own}) == before
    assert client.post(f"/admin/case/{own}/close/", json={"reason": "Forged"}).status_code == 403
    page = client.get(f"/admin/case/{own}/").get_data(as_text=True)
    assert not re.search(r'<form[^>]+action="[^"]+/add_action/', page)
    assert 'onclick="promptCaseAction(' not in page


def test_unlinked_case_and_global_tools_remain_outside_city_scope(app, db, seeded_data):
    client, _actor, own, _foreign, _demo = _city_cases(app, db, seeded_data)
    db.cases.update_one({"_id": own}, {"$unset": {"demo_id": ""}})
    assert client.get(f"/admin/case/{own}/").status_code == 403
    assert client.get("/admin/case/blocklist/").status_code == 403


def test_city_case_reply_and_close_reopen_are_scoped_and_persisted(app, db, seeded_data):
    client, _actor, own, _foreign, _demo = _city_cases(app, db, seeded_data)
    db.cases.update_one({"_id": own}, {"$set": {
        "type": "support_ticket", "submitter": {"submitter_email": "alice@example.test"},
    }})
    reply = client.post(f"/admin/case/{own}/reply/", data={"reply_message": "Scoped reply"})
    assert reply.status_code == 302
    doc = db.cases.find_one({"_id": own})
    assert any(message.get("direction") == "out" for message in doc["suggestion"]["messages"])
    assert client.post(f"/admin/case/{own}/close/", json={"reason": "Complete"}).status_code == 200
    assert db.cases.find_one({"_id": own})["meta"]["closed"] is True
    assert client.post(f"/admin/case/{own}/reopen/", json={"reason": "Follow up"}).status_code == 200
    assert db.cases.find_one({"_id": own})["meta"]["closed"] is False


def test_city_key_is_authoritative_over_conflicting_city_text(app, db, seeded_data):
    client, _actor, own, _foreign, _demo = _city_cases(app, db, seeded_data)
    db.demonstrations.update_one({"_id": seeded_data["pending_demo_id"]}, {"$set": {
        "city": "Helsinki", "city_key": "turku",
    }})
    assert client.get(f"/admin/case/{own}/").status_code == 403
