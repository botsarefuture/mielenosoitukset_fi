"""SEC-04: regression tests for token and approval lifecycles.

One test per documented behaviour in docs/token-lifecycle.md: expiry, replay,
revocation and repeated decisions for each bearer link.
"""

from datetime import timedelta

import jwt
import pytest


def _expired_jwt(app, claims):
    from mielenosoitukset_fi.utils.time_utils import utcnow

    return jwt.encode(
        {**claims, "exp": utcnow() - timedelta(minutes=1)},
        app.config["SECRET_KEY"],
        algorithm="HS256",
    )


# --- Organizer cancellation link -------------------------------------------


def test_cancellation_link_is_single_use(client, db, seeded_data):
    token = seeded_data["cancel_token"]
    first = client.post(f"/cancel_demonstration/{token}", data={"reason": "x"})
    assert first.status_code == 302
    used = db.demo_cancellation_tokens.find_one({"demo_id": seeded_data["demo_id"]})
    assert used["used_at"] is not None

    replay = client.post(f"/cancel_demonstration/{token}", data={"reason": "again"})
    assert replay.status_code == 200
    assert "jo käytetty" in replay.get_data(as_text=True)
    after = db.demo_cancellation_tokens.find_one({"_id": used["_id"]})
    assert after["used_at"] == used["used_at"]
    assert after["used_reason"] == "x"


def test_expired_cancellation_link_cannot_cancel(client, db, seeded_data):
    from mielenosoitukset_fi.utils.time_utils import utcnow

    db.demo_cancellation_tokens.update_many(
        {}, {"$set": {"expires_at": utcnow() - timedelta(seconds=1)}}
    )
    response = client.post(
        f"/cancel_demonstration/{seeded_data['cancel_token']}", data={"reason": "x"}
    )
    assert response.status_code == 200
    assert "vanhentunut" in response.get_data(as_text=True)
    demo = db.demonstrations.find_one({"_id": seeded_data["demo_id"]})
    assert not demo.get("cancelled")
    assert db.demo_cancellation_tokens.find_one({})["used_at"] is None


def test_unknown_cancellation_link_changes_nothing(client, db, seeded_data):
    response = client.post("/cancel_demonstration/not-a-token", data={"reason": "x"})
    assert response.status_code == 200
    assert not db.demonstrations.find_one({"_id": seeded_data["demo_id"]}).get(
        "cancelled"
    )


# --- Demonstration approve / reject / preview / edit links ------------------


@pytest.mark.parametrize("route", ["approve", "reject", "preview"])
def test_expired_magic_link_is_gone_and_does_not_decide(
    client, db, seeded_data, route
):
    from mielenosoitukset_fi.utils.time_utils import utcnow

    db.magic_links.update_many(
        {"demo_id": str(seeded_data["pending_demo_id"])},
        {"$set": {"expires_at": utcnow() - timedelta(seconds=1)}},
    )
    token = seeded_data[f"{route}_token"]
    response = client.get(f"/admin/demo/{route}_demo_with_token/{token}")
    assert response.status_code == 410
    if route != "preview":
        post = client.post(f"/admin/demo/{route}_demo_with_token/{token}")
        assert post.status_code == 410
    demo = db.demonstrations.find_one({"_id": seeded_data["pending_demo_id"]})
    assert not demo.get("approved") and not demo.get("rejected")
    assert "moderation_decision" not in demo


def test_revoked_magic_link_is_forbidden_and_does_not_decide(
    client, db, seeded_data
):
    db.magic_links.update_many(
        {"demo_id": str(seeded_data["pending_demo_id"])}, {"$set": {"revoked": True}}
    )
    response = client.post(
        f"/admin/demo/approve_demo_with_token/{seeded_data['approve_token']}"
    )
    assert response.status_code == 403
    demo = db.demonstrations.find_one({"_id": seeded_data["pending_demo_id"]})
    assert not demo.get("approved")


def test_unregistered_but_validly_signed_magic_link_is_rejected(
    client, db, seeded_data
):
    from mielenosoitukset_fi.admin.admin_demo_bp import serializer

    forged = serializer.dumps(
        str(seeded_data["pending_demo_id"]), salt="approve-demo"
    ) + "x"
    assert client.post(f"/admin/demo/approve_demo_with_token/{forged}").status_code == 400
    # A correctly signed token that never reached the registry is also refused.
    unregistered = serializer.dumps(
        str(seeded_data["pending_demo_id"]), salt="approve-demo-unregistered"
    )
    assert (
        client.post(f"/admin/demo/approve_demo_with_token/{unregistered}").status_code
        == 400
    )
    assert not db.demonstrations.find_one(
        {"_id": seeded_data["pending_demo_id"]}
    ).get("approved")


def test_magic_link_cannot_be_used_for_another_action(client, db, seeded_data):
    response = client.post(
        f"/admin/demo/reject_demo_with_token/{seeded_data['approve_token']}"
    )
    assert response.status_code == 400
    demo = db.demonstrations.find_one({"_id": seeded_data["pending_demo_id"]})
    assert not demo.get("rejected")


def test_approval_link_replay_does_not_repeat_the_decision(
    client, db, seeded_data, monkeypatch
):
    from importlib import import_module

    queued = []
    for name in ("mielenosoitukset_fi.admin.admin_demo_bp", "admin.admin_demo_bp"):
        monkeypatch.setattr(
            import_module(name).email_sender, "queue_email", lambda **k: queued.append(k)
        )
    url = f"/admin/demo/approve_demo_with_token/{seeded_data['approve_token']}"
    assert client.post(url).status_code == 302
    decision = db.demonstrations.find_one({"_id": seeded_data["pending_demo_id"]})[
        "moderation_decision"
    ]
    assert client.post(url).status_code == 200
    assert client.post(url).status_code == 200
    after = db.demonstrations.find_one({"_id": seeded_data["pending_demo_id"]})
    assert after["moderation_decision"] == decision
    assert len(queued) <= 1


# --- Password reset and e-mail confirmation (signed JWT, one hour) ----------


def test_reset_token_is_single_use(client, db, seeded_data):
    token = seeded_data["reset_token"]
    new_password = "Zq7-correct-horse-battery-staple"
    first = client.post(
        f"/users/auth/password_reset/{token}",
        data={"password": new_password, "password_confirm": new_password},
    )
    assert first.status_code == 302
    assert db.used_password_change_tokens.count_documents({"token": token}) == 1
    before = db.users.find_one({"email": "alice@example.test"})["password_hash"]

    other = "Another-Strong-Passphrase-9!"
    replay = client.post(
        f"/users/auth/password_reset/{token}",
        data={"password": other, "password_confirm": other},
    )
    assert replay.status_code == 302
    assert db.users.find_one({"email": "alice@example.test"})["password_hash"] == before
    assert db.used_password_change_tokens.count_documents({"token": token}) == 1


def test_expired_and_garbage_reset_tokens_change_nothing(app, client, db):
    before = db.users.find_one({"email": "alice@example.test"})["password_hash"]
    password = "Zq7-correct-horse-battery-staple"
    for token in (
        _expired_jwt(app, {"email": "alice@example.test", "purpose": "password_reset"}),
        "garbage",
    ):
        response = client.post(
            f"/users/auth/password_reset/{token}",
            data={"password": password, "password_confirm": password},
        )
        assert response.status_code == 302
    assert db.users.find_one({"email": "alice@example.test"})["password_hash"] == before
    assert db.used_password_change_tokens.count_documents({}) == 0


def test_reset_and_confirmation_tokens_are_not_interchangeable(app):
    from mielenosoitukset_fi.utils.auth import (
        generate_confirmation_token,
        generate_reset_token,
        verify_confirmation_token,
        verify_reset_token,
    )

    with app.app_context():
        reset = generate_reset_token("a@example.test")
        confirm = generate_confirmation_token("a@example.test")
        assert verify_reset_token(reset) == "a@example.test"
        assert verify_confirmation_token(confirm) == "a@example.test"
        assert verify_reset_token(confirm) is None
        assert verify_confirmation_token(reset) is None


def test_links_issued_before_the_purpose_claim_still_work(app):
    from mielenosoitukset_fi.utils.auth import (
        _generate_token,
        verify_confirmation_token,
        verify_reset_token,
    )

    with app.app_context():
        legacy = _generate_token({"email": "a@example.test"}, 3600)
        assert verify_reset_token(legacy) == "a@example.test"
        assert verify_confirmation_token(legacy) == "a@example.test"


def test_expired_confirmation_link_does_not_confirm(app, client, db):
    db.users.update_one({"email": "alice@example.test"}, {"$set": {"confirmed": False}})
    token = _expired_jwt(
        app, {"email": "alice@example.test", "purpose": "email_confirmation"}
    )
    client.get(f"/users/auth/confirm_email/{token}")
    assert db.users.find_one({"email": "alice@example.test"})["confirmed"] is False


def test_confirmation_link_replay_is_harmless(client, db, seeded_data):
    db.users.update_one({"email": "alice@example.test"}, {"$set": {"confirmed": False}})
    url = f"/users/auth/confirm_email/{seeded_data['confirmation_token']}"
    assert client.get(url).status_code == 302
    assert client.get(url).status_code == 302
    assert db.users.find_one({"email": "alice@example.test"})["confirmed"] is True


# --- Campaign volunteer confirmation ----------------------------------------


def _volunteer(db, **extra):
    from mielenosoitukset_fi.utils.time_utils import utcnow

    doc = {
        "name": "V",
        "email": "v@example.test",
        "confirmed": False,
        "confirmation_token": "vol-token",
        "confirmation_expires": utcnow() + timedelta(hours=1),
        **extra,
    }
    db.volunteers.insert_one(doc)
    return doc


def test_volunteer_confirmation_is_consumed_on_use(client, db):
    _volunteer(db)
    assert client.get("/kampanja/confirm/vol-token").status_code == 200
    volunteer = db.volunteers.find_one({"email": "v@example.test"})
    assert volunteer["confirmed"] is True
    assert "confirmation_token" not in volunteer
    assert client.get("/kampanja/confirm/vol-token").status_code == 400


def test_expired_volunteer_confirmation_does_not_confirm(client, db):
    from mielenosoitukset_fi.utils.time_utils import utcnow

    _volunteer(db, confirmation_expires=utcnow() - timedelta(seconds=1))
    assert client.get("/kampanja/confirm/vol-token").status_code == 400
    assert db.volunteers.find_one({"email": "v@example.test"})["confirmed"] is False


def test_cancellation_link_is_claimed_atomically(client, db, seeded_data):
    from mielenosoitukset_fi.utils.demo_cancellation import (
        claim_cancellation_token,
        release_cancellation_token,
    )

    record = db.demo_cancellation_tokens.find_one({})
    assert claim_cancellation_token(record["_id"]) is True
    assert claim_cancellation_token(record["_id"]) is False
    release_cancellation_token(record["_id"])
    assert db.demo_cancellation_tokens.find_one({"_id": record["_id"]})["used_at"] is None
    assert claim_cancellation_token(record["_id"]) is True


def test_failed_cancellation_releases_the_link(client, db, seeded_data, monkeypatch):
    from importlib import import_module

    def boom(*args, **kwargs):
        raise RuntimeError("down")

    for name in ("mielenosoitukset_fi.basic_routes", "basic_routes"):
        try:
            monkeypatch.setattr(import_module(name), "cancel_demo", boom)
        except ImportError:
            pass
    client.post(f"/cancel_demonstration/{seeded_data['cancel_token']}", data={"reason": "x"})
    assert db.demo_cancellation_tokens.find_one({})["used_at"] is None
