"""Content rollback must not replay authority or moderation from history."""

from copy import deepcopy
from html.parser import HTMLParser

import pytest
from bson import ObjectId

from tests.conftest import _client_for_user
from tests.test_city_scoped_admin import _create_scoped_admin
from tests.test_demo_decision_service import _capture_decision_email


def _rollback(client, history_id):
    with client.session_transaction() as session:
        session["demo_rollback_csrf_token"] = "synthetic-rollback-csrf"
    return client.post(f"/admin/demo/rollback_demo/{history_id}", data={
        "csrf_token": "synthetic-rollback-csrf",
    })


@pytest.mark.parametrize("decision", ["approve", "deny"])
def test_rollback_preserves_current_decision_scope_and_metadata(
    admin_client, db, seeded_data, monkeypatch, decision
):
    queued = _capture_decision_email(monkeypatch)
    demo_id = seeded_data["pending_demo_id"]
    assert admin_client.post(f"/api/admin/demo/{demo_id}/{decision}").status_code == 200
    db.demonstrations.update_one({"_id": demo_id}, {"$set": {
        "server_owned": {"keep": True}, "cancelled": True,
        "editors": [str(seeded_data["friend_id"])],
    }})
    before = db.demonstrations.find_one({"_id": demo_id})
    cases = list(db.cases.find({}))
    links = list(db.magic_links.find({}))
    historical = deepcopy(before)
    historical.update({
        "_id": ObjectId(), "title": "Restored content", "description": None,
        "approved": decision != "approve", "rejected": decision == "approve",
        "moderation_decision": {"obsolete": True}, "server_owned": "obsolete",
        "city": "Turku", "city_key": "turku", "organizers": [], "editors": [],
        "cancelled": False, "hide": not before.get("hide", False),
        "slug": "obsolete-slug", "parent": ObjectId(),
    })
    history_id = db.demo_edit_history.insert_one({
        "demo_id": str(demo_id), "old_demo": historical,
    }).inserted_id
    response = _rollback(admin_client, history_id)
    assert response.status_code == 302
    after = db.demonstrations.find_one({"_id": demo_id})
    assert after["title"] == "Restored content"
    assert after["description"] is None
    assert after["last_modified"] >= before.get("last_modified", after["last_modified"])
    assert {k: v for k, v in after.items() if k not in {"title", "description", "last_modified"}} == {
        k: v for k, v in before.items() if k not in {"title", "description", "last_modified"}
    }
    assert list(db.cases.find({})) == cases
    assert list(db.magic_links.find({})) == links
    assert len(queued) == 1
    entry = db.demo_edit_history.find_one({"rollbacked_from": history_id})
    assert entry["old_demo"] == before
    assert entry["new_demo"] == after
    assert entry["edited_by"] == str(seeded_data["admin_id"])
    # Repeating the same restore has no content change and creates no duplicate.
    assert _rollback(admin_client, history_id).status_code == 302
    assert db.demo_edit_history.count_documents({"rollbacked_from": history_id}) == 1


def test_rollback_sparse_history_and_undo_use_actual_content(admin_client, db, seeded_data):
    demo_id = seeded_data["demo_id"]
    before = db.demonstrations.find_one({"_id": demo_id})
    history_id = seeded_data["history_id"]
    db.demo_edit_history.update_one({"_id": history_id}, {"$set": {
        "old_demo": {"title": "Sparse historical title"},
    }})
    assert _rollback(admin_client, history_id).status_code == 302
    after = db.demonstrations.find_one({"_id": demo_id})
    assert after["title"] == "Sparse historical title"
    assert {k: v for k, v in after.items() if k not in {"title", "last_modified"}} == {
        k: v for k, v in before.items() if k not in {"title", "last_modified"}
    }
    entry = db.demo_edit_history.find_one({"rollbacked_from": history_id})
    assert _rollback(admin_client, entry['_id']).status_code == 302
    assert db.demonstrations.find_one({"_id": demo_id})["title"] == before["title"]


@pytest.mark.parametrize("field,old_value,new_value", [
    ("latitude", "60.1699", "61.4978"),
    ("longitude", "24.9384", "23.7610"),
    ("img", "old-image.png", "new-image.png"),
    ("cover_source", "user", "automatic"),
    ("event_type", "MARCH", "STAY_STILL"),
])
def test_rollback_restores_canonical_location_and_media_content(
    admin_client, db, seeded_data, field, old_value, new_value
):
    demo_id = seeded_data["demo_id"]
    db.demonstrations.update_one({"_id": demo_id}, {"$set": {field: new_value}})
    before = db.demonstrations.find_one({"_id": demo_id})
    history_id = db.demo_edit_history.insert_one({
        "demo_id": str(demo_id), "old_demo": {field: old_value},
    }).inserted_id
    assert _rollback(admin_client, history_id).status_code == 302
    after = db.demonstrations.find_one({"_id": demo_id})
    assert after[field] == old_value
    assert {key: value for key, value in after.items() if key not in {field, "last_modified"}} == {
        key: value for key, value in before.items() if key not in {field, "last_modified"}
    }
    entry = db.demo_edit_history.find_one({"rollbacked_from": history_id})
    assert entry["old_demo"] == before
    assert entry["new_demo"] == after
    assert _rollback(admin_client, entry["_id"]).status_code == 302
    assert db.demonstrations.find_one({"_id": demo_id})[field] == new_value


@pytest.mark.parametrize("field,value", [
    ("latitude", "61.4978"), ("longitude", "23.7610"),
    ("img", "concurrent.png"), ("cover_source", "automatic"), ("event_type", "MARCH"),
])
def test_rollback_guards_canonical_location_and_media_changes(
    admin_client, db, seeded_data, monkeypatch, field, value
):
    demo_id = seeded_data["demo_id"]
    db.demonstrations.update_one({"_id": demo_id}, {"$unset": {field: ""}})
    before = db.demonstrations.find_one({"_id": demo_id})
    history_id = db.demo_edit_history.insert_one({
        "demo_id": str(demo_id), "old_demo": {"title": "Must not cross content versions"},
    }).inserted_id
    collection_type = type(db.demonstrations)
    original = collection_type.find_one_and_update

    def interleave(collection, query, *args, **kwargs):
        if collection.name == "demonstrations" and query.get("_id") == demo_id:
            collection.update_one({"_id": demo_id}, {"$set": {field: value}})
        return original(collection, query, *args, **kwargs)

    monkeypatch.setattr(collection_type, "find_one_and_update", interleave)
    assert _rollback(admin_client, history_id).status_code == 409
    assert db.demonstrations.find_one({"_id": demo_id}) == {**before, field: value}
    assert db.demo_edit_history.count_documents({"rollbacked_from": history_id}) == 0


@pytest.mark.parametrize("foreign", [False, True])
def test_rollback_checks_current_city_scope(app, db, seeded_data, foreign):
    actor = _create_scoped_admin(db, ["helsinki"], ["EDIT_DEMO"])
    client = _client_for_user(app, actor)
    demo_id = seeded_data["demo_id"]
    # A historical in-scope city cannot grant access to a foreign current target.
    db.demonstrations.update_one({"_id": demo_id}, {"$set": {
        "city": "Turku" if foreign else "Helsinki",
        "city_key": "turku" if foreign else "helsinki", "editors": [],
    }})
    history_id = seeded_data["history_id"]
    db.demo_edit_history.update_one({"_id": history_id}, {"$set": {
        "old_demo": {"title": "Scoped restore", "city": "Helsinki"},
    }})
    before = db.demonstrations.find_one({"_id": demo_id})
    response = _rollback(client, history_id)
    assert response.status_code == (403 if foreign else 302)
    after = db.demonstrations.find_one({"_id": demo_id})
    if foreign:
        assert after == before
        assert db.demo_edit_history.count_documents({"rollbacked_from": history_id}) == 0
    else:
        assert after["title"] == "Scoped restore"
        assert after["city_key"] == "helsinki"


@pytest.mark.parametrize("change", [{"title": "Concurrent edit"}, {"city_key": "turku"}])
def test_rollback_conflict_does_not_write_or_record_success(
    admin_client, db, seeded_data, monkeypatch, change
):
    demo_id = seeded_data["demo_id"]
    history_id = seeded_data["history_id"]
    db.demo_edit_history.update_one({"_id": history_id}, {"$set": {
        "old_demo": {"title": "Must not overwrite a concurrent change"},
    }})
    collection = db.demonstrations
    original = type(collection).find_one_and_update

    def interleave(self, query, update, *args, **kwargs):
        if self.name == "demonstrations" and "$and" in query:
            self.update_one({"_id": demo_id}, {"$set": change})
        return original(self, query, update, *args, **kwargs)

    monkeypatch.setattr(type(collection), "find_one_and_update", interleave)
    response = _rollback(admin_client, history_id)
    assert response.status_code == 409
    after = db.demonstrations.find_one({"_id": demo_id})
    assert all(after[key] == value for key, value in change.items())
    assert after["title"] != "Must not overwrite a concurrent change"
    assert db.demo_edit_history.count_documents({"rollbacked_from": history_id}) == 0


@pytest.mark.parametrize("kind", ["invalid", "missing", "invalid-target", "missing-target"])
def test_rollback_invalid_identifiers_are_not_server_errors(admin_client, db, kind):
    history_id = "not-an-id" if kind == "invalid" else ObjectId()
    if kind.endswith("target"):
        db.demo_edit_history.insert_one({
            "_id": history_id,
            "demo_id": "invalid" if kind == "invalid-target" else str(ObjectId()),
            "old_demo": {"title": "No target"},
        })
    assert admin_client.post(f"/admin/demo/rollback_demo/{history_id}").status_code == 404


def test_rollback_keeps_concurrent_unrelated_metadata(admin_client, db, seeded_data, monkeypatch):
    demo_id = seeded_data["demo_id"]
    history_id = seeded_data["history_id"]
    db.demo_edit_history.update_one({"_id": history_id}, {"$set": {
        "old_demo": {"title": "Restored content with fresh metadata"},
    }})
    collection = db.demonstrations
    original = type(collection).find_one_and_update

    def interleave(self, query, update, *args, **kwargs):
        if self.name == "demonstrations" and "$and" in query:
            self.update_one({"_id": demo_id}, {"$set": {"server_owned": "fresh metadata"}})
        return original(self, query, update, *args, **kwargs)

    monkeypatch.setattr(type(collection), "find_one_and_update", interleave)
    assert _rollback(admin_client, history_id).status_code == 302
    after = db.demonstrations.find_one({"_id": demo_id})
    assert after["title"] == "Restored content with fresh metadata"
    assert after["server_owned"] == "fresh metadata"
    entry = db.demo_edit_history.find_one({"rollbacked_from": history_id})
    assert entry["old_demo"]["server_owned"] == "fresh metadata"
    assert entry["new_demo"] == after


def test_rollback_requires_edit_permission_and_csrf(app, admin_client, user_client, db, seeded_data):
    history_id = seeded_data["history_id"]
    before = db.demonstrations.find_one({"_id": seeded_data["demo_id"]})
    assert user_client.post(f"/admin/demo/rollback_demo/{history_id}").status_code == 403
    assert admin_client.post(f"/admin/demo/rollback_demo/{history_id}").status_code == 400
    for invalid_token in ("incorrect-token", "väärä-token"):
        assert admin_client.post(f"/admin/demo/rollback_demo/{history_id}", data={
            "csrf_token": invalid_token,
        }).status_code == 400
    page = admin_client.get(f"/admin/demo/view_demo_diff/{history_id}").get_data(as_text=True)
    class RollbackForm(HTMLParser):
        in_form = False
        token = None

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "form":
                self.in_form = attrs.get("action") == f"/admin/demo/rollback_demo/{history_id}"
            elif self.in_form and tag == "input" and attrs.get("name") == "csrf_token":
                self.token = attrs.get("value")

        def handle_endtag(self, tag):
            if tag == "form":
                self.in_form = False

    form = RollbackForm()
    form.feed(page)
    token = form.token
    assert token
    assert db.demonstrations.find_one({"_id": seeded_data["demo_id"]}) == before
    assert admin_client.post(f"/admin/demo/rollback_demo/{history_id}", data={"csrf_token": token}).status_code == 302


@pytest.mark.parametrize("locale,expected", [
    ("fi", "Palautus koskee vain versioon tallennettua tapahtumasisältöä."),
    ("en", "Only event content recorded in this version is restored."),
    ("sv", "Endast evenemangsinnehåll som sparats i versionen återställs."),
])
def test_rollback_explanation_uses_compiled_locale(app, admin_client, seeded_data, locale, expected):
    app.config.update(BABEL_PUBLIC_LOCALES=["fi", "en", "sv"])
    with admin_client.session_transaction() as session:
        session["locale"] = locale
    response = admin_client.get(f"/admin/demo/view_demo_diff/{seeded_data['history_id']}")
    assert response.status_code == 200
    assert expected in response.get_data(as_text=True)
