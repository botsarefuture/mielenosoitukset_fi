from importlib import import_module

from bson import ObjectId

from tests.conftest import _client_for_user, _seed_database, _user_doc
from mielenosoitukset_fi.users.models import User

admin_user_module = import_module("mielenosoitukset_fi.admin.admin_user_bp")
board_compliance = import_module("mielenosoitukset_fi.admin.board_compliance")
board_audit_module = import_module("mielenosoitukset_fi.admin.board_audit")


def _bind_board_modules_to_test_db(monkeypatch, db):
    monkeypatch.setattr(board_compliance, "mongo", db, raising=False)
    monkeypatch.setattr(board_audit_module, "mongo", db, raising=False)
    monkeypatch.setattr(admin_user_module, "mongo", db, raising=False)


def _insert_board_member(db, username, email):
    user_id = ObjectId()
    db.users.insert_one(
        _user_doc(
            username,
            email,
            "BoardPass1!",
            _id=user_id,
            role="board_member",
            global_admin=False,
        )
    )
    return user_id


def test_board_member_role_gets_clearance_permissions(db, monkeypatch):
    _bind_board_modules_to_test_db(monkeypatch, db)
    user_id = ObjectId()
    db.users.insert_one(
        _user_doc(
            "board-alice",
            "board-alice@example.test",
            "BoardPass1!",
            _id=user_id,
            role="board_member",
            global_admin=False,
        )
    )

    user = User.from_db(db.users.find_one({"_id": user_id}))
    assert user.has_permission("MANAGE_CLEARANCE") is True
    assert user.has_permission("VIEW_CLEARANCE_AUDIT") is True
    assert user.global_admin is False


def test_board_member_can_access_board_ui_and_audit_ui(app, db, monkeypatch):
    _bind_board_modules_to_test_db(monkeypatch, db)
    board_member_id = _insert_board_member(db, "board-ui", "board-ui@example.test")
    client = _client_for_user(app, board_member_id)

    clearance_response = client.get("/board/ui")
    audit_response = client.get("/board/audit/ui")

    assert clearance_response.status_code == 200
    assert audit_response.status_code == 200


def test_board_request_approval_auto_assigns_god(app, db, monkeypatch):
    _bind_board_modules_to_test_db(monkeypatch, db)
    seeded = _seed_database(app, db)
    target_id = seeded["user_id"]
    board_a = _insert_board_member(db, "board-a", "board-a@example.test")
    board_b = _insert_board_member(db, "board-b", "board-b@example.test")

    creator_client = _client_for_user(app, seeded["admin_id"])
    create_response = creator_client.post(
        f"/board/api/clearance/{target_id}",
        json={
            "request_type": "assign_role",
            "requested_role": "god",
            "approval_document_url": "https://example.test/board/god.pdf",
            "approval_document_sha256": "deadbeef",
            "reason": "Emergency access for release rollback",
        },
    )
    assert create_response.status_code == 200
    request_id = create_response.get_json()["request"]["id"]

    board_a_client = _client_for_user(app, board_a)
    first_vote = board_a_client.post(
        f"/board/api/clearance/request/{request_id}/decision",
        json={"decision": "approve"},
    )
    assert first_vote.status_code == 200
    assert first_vote.get_json()["request"]["status"] == "pending"

    board_b_client = _client_for_user(app, board_b)
    second_vote = board_b_client.post(
        f"/board/api/clearance/request/{request_id}/decision",
        json={"decision": "approve"},
    )
    assert second_vote.status_code == 200
    assert second_vote.get_json()["request"]["status"] == "approved"

    updated_user = db.users.find_one({"_id": target_id})
    assert updated_user["role"] == "god"
    assert board_compliance.has_board_clearance(target_id) is True
    assert User.from_db(updated_user).global_admin is True


def test_board_request_approval_auto_assigns_global_admin(app, db, monkeypatch):
    _bind_board_modules_to_test_db(monkeypatch, db)
    seeded = _seed_database(app, db)
    target_id = seeded["user_id"]
    board_a = _insert_board_member(db, "board-c", "board-c@example.test")
    board_b = _insert_board_member(db, "board-d", "board-d@example.test")

    creator_client = _client_for_user(app, seeded["admin_id"])
    create_response = creator_client.post(
        f"/board/api/clearance/{target_id}",
        json={
            "request_type": "assign_role",
            "requested_role": "global_admin",
            "approval_document_url": "https://example.test/board/global-admin.pdf",
            "approval_document_sha256": "cafebabe",
            "reason": "Permanent senior admin appointment",
        },
    )
    request_id = create_response.get_json()["request"]["id"]

    _client_for_user(app, board_a).post(
        f"/board/api/clearance/request/{request_id}/decision",
        json={"decision": "approve"},
    )
    final_vote = _client_for_user(app, board_b).post(
        f"/board/api/clearance/request/{request_id}/decision",
        json={"decision": "approve"},
    )

    assert final_vote.status_code == 200
    updated_user = db.users.find_one({"_id": target_id})
    assert updated_user["role"] == "global_admin"
    assert User.from_db(updated_user).global_admin is True


def test_revoke_god_request_demotes_user_after_all_board_votes(app, db, monkeypatch):
    _bind_board_modules_to_test_db(monkeypatch, db)
    seeded = _seed_database(app, db)
    target_id = seeded["user_id"]
    db.users.update_one({"_id": target_id}, {"$set": {"role": "god", "global_admin": False}})

    board_a = _insert_board_member(db, "board-e", "board-e@example.test")
    board_b = _insert_board_member(db, "board-f", "board-f@example.test")

    creator_client = _client_for_user(app, seeded["admin_id"])
    grant_response = creator_client.post(
        f"/board/api/clearance/{target_id}",
        json={
            "request_type": "assign_role",
            "requested_role": "god",
            "approval_document_url": "https://example.test/board/god.pdf",
            "approval_document_sha256": "deadbeef",
        },
    )
    grant_request_id = grant_response.get_json()["request"]["id"]
    _client_for_user(app, board_a).post(
        f"/board/api/clearance/request/{grant_request_id}/decision",
        json={"decision": "approve"},
    )
    _client_for_user(app, board_b).post(
        f"/board/api/clearance/request/{grant_request_id}/decision",
        json={"decision": "approve"},
    )

    revoke_response = creator_client.post(
        f"/board/api/clearance/{target_id}",
        json={
            "request_type": "revoke_god",
            "fallback_role": "admin",
            "approval_document_url": "https://example.test/board/revoke.pdf",
            "approval_document_sha256": "beadfeed",
            "reason": "Emergency access no longer needed",
        },
    )
    revoke_request_id = revoke_response.get_json()["request"]["id"]

    _client_for_user(app, board_a).post(
        f"/board/api/clearance/request/{revoke_request_id}/decision",
        json={"decision": "approve"},
    )
    final_vote = _client_for_user(app, board_b).post(
        f"/board/api/clearance/request/{revoke_request_id}/decision",
        json={"decision": "approve"},
    )

    assert final_vote.status_code == 200
    updated_user = db.users.find_one({"_id": target_id})
    assert updated_user["role"] == "admin"
    assert board_compliance.has_board_clearance(target_id) is False


def test_tampered_board_request_loses_clearance_and_blocks_further_votes(app, db, monkeypatch):
    _bind_board_modules_to_test_db(monkeypatch, db)
    seeded = _seed_database(app, db)
    target_id = seeded["user_id"]
    board_a = _insert_board_member(db, "board-g", "board-g@example.test")
    board_b = _insert_board_member(db, "board-h", "board-h@example.test")

    creator_client = _client_for_user(app, seeded["admin_id"])
    create_response = creator_client.post(
        f"/board/api/clearance/{target_id}",
        json={
            "request_type": "assign_role",
            "requested_role": "god",
            "approval_document_url": "https://example.test/board/god.pdf",
            "approval_document_sha256": "deadbeef",
            "reason": "Temporary emergency access",
        },
    )
    request_id = create_response.get_json()["request"]["id"]

    _client_for_user(app, board_a).post(
        f"/board/api/clearance/request/{request_id}/decision",
        json={"decision": "approve"},
    )
    _client_for_user(app, board_b).post(
        f"/board/api/clearance/request/{request_id}/decision",
        json={"decision": "approve"},
    )

    db.board_clearance_requests.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": {"approval_document_sha256": "tampered"}},
    )

    assert board_compliance.has_board_clearance(target_id) is False

    db.board_clearance_requests.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": {"status": "pending"}},
    )
    blocked_vote = _client_for_user(app, board_a).post(
        f"/board/api/clearance/request/{request_id}/decision",
        json={"decision": "approve"},
    )
    assert blocked_vote.status_code == 409


def test_manual_god_promotion_is_rejected_from_user_edit(admin_client, db, monkeypatch):
    _bind_board_modules_to_test_db(monkeypatch, db)
    target_id = ObjectId()
    db.users.insert_one(
        _user_doc(
            "manual-target",
            "manual-target@example.test",
            "UserPass1!",
            _id=target_id,
            role="admin",
            global_admin=False,
        )
    )

    response = admin_client.post(
        f"/admin/user/save_user/{target_id}",
        data={
            "username": "manual-target",
            "email": "manual-target@example.test",
            "role": "god",
        },
        follow_redirects=False,
    )

    assert response.status_code in {302, 303}
    updated_user = db.users.find_one({"_id": target_id})
    assert updated_user["role"] == "admin"


def test_compare_user_levels_keeps_magic_id_from_bypassing_checks():
    magic_id = ObjectId("66c25768dad432ad39ce38d5")
    magic_admin = type(
        "UserStub",
        (),
        {"_id": magic_id, "role": "global_admin", "is_authenticated": True, "global_admin": False},
    )()
    peer_admin = type(
        "UserStub",
        (),
        {"_id": ObjectId(), "role": "global_admin", "is_authenticated": True, "global_admin": False},
    )()

    assert admin_user_module.compare_user_levels(magic_admin, peer_admin) is False
