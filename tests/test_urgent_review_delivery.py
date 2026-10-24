from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from bson import ObjectId
import pytest
import requests

from mielenosoitukset_fi.scripts import process_urgent_review_alerts as worker
from mielenosoitukset_fi.utils.urgent_review_telegram import DeliveryFailure, TelegramReviewTransport

NOW = datetime(2026, 10, 24, 10, tzinfo=UTC)
CHAT = -100000123


@pytest.fixture(autouse=True)
def delivery_database(seeded_data):
    """Use the real isolated Mongo fixture, reset before each delivery case."""


def _demo(db, remaining=30, **changes):
    start = (NOW + timedelta(hours=remaining)).astimezone(worker.HELSINKI)
    doc = {
        "_id": ObjectId(), "title": "Urgent review", "city": "Helsinki",
        "date": start.date().isoformat(), "start_time": start.strftime("%H:%M"),
        "approved": False, "rejected": False, "cancelled": False, **changes,
    }
    db.demonstrations.insert_one(doc)
    return doc["_id"]


class Provider:
    chat_id = CHAT

    def __init__(self, failures=()):
        self.calls = []
        self.failures = list(failures)
        self.next_id = 123

    def deliver(self, text, message_id=None):
        self.calls.append((text, message_id))
        if self.failures:
            raise self.failures.pop(0)
        if message_id is not None:
            return message_id
        receipt = self.next_id
        self.next_id += 1
        return receipt


def test_discovery_crosses_threshold_without_edits_and_deduplicates(db):
    demo_id = _demo(db, remaining=49, in_past=True)
    worker.discover(db, CHAT, NOW)
    assert db.urgent_review_outbox.count_documents({}) == 0
    worker.discover(db, CHAT, NOW + timedelta(hours=2))
    worker.discover(db, CHAT, NOW + timedelta(hours=2))
    assert db.urgent_review_outbox.count_documents({"demo_id": demo_id}) == 1
    job = db.urgent_review_outbox.find_one({"demo_id": demo_id})
    assert job["status"] == "ready"
    assert not {"title", "description", "submitter_email", "text"}.intersection(job)


def test_discovery_keyset_is_bounded_and_eventually_reaches_every_candidate(db, monkeypatch):
    db.demonstrations.delete_many({})
    ids = {_demo(db) for _ in range(5)}
    monkeypatch.setattr(worker, "DISCOVERY_BATCH", 2)
    worker.discover(db, CHAT, NOW)
    assert db.urgent_review_outbox.count_documents({}) == 2
    worker.discover(db, CHAT, NOW)
    assert db.urgent_review_outbox.count_documents({}) == 4
    worker.discover(db, CHAT, NOW)
    assert {row["demo_id"] for row in db.urgent_review_outbox.find({})} == ids
    assert db.urgent_review_cursors.find_one({"_id": CHAT})["after"] is None


def test_provider_receipt_is_reused_for_critical_and_resolved_edits(db):
    demo_id = _demo(db, remaining=25)
    provider = Provider()
    worker.discover(db, CHAT, NOW)
    worker.reconcile(db, provider, NOW)
    worker.reconcile(db, provider, NOW + timedelta(minutes=3))
    assert len(provider.calls) == 1  # unchanged hash does not edit every tick
    worker.reconcile(db, provider, NOW + timedelta(hours=2))
    assert "alle 24 h" in provider.calls[-1][0]
    assert provider.calls[-1][1] == 123
    db.demonstrations.update_one({"_id": demo_id}, {"$set": {"approved": True}})
    worker.reconcile(db, provider, NOW + timedelta(hours=2, minutes=3))
    assert "Hyväksytty" in provider.calls[-1][0]
    assert [call[1] for call in provider.calls] == [None, 123, 123]
    assert db.urgent_review_outbox.find_one({"demo_id": demo_id})["state"] == "approved"


def test_latest_canonical_state_suppresses_stale_new_send_and_reopens_watch(db):
    demo_id = _demo(db)
    provider = Provider()
    worker.discover(db, CHAT, NOW)
    db.demonstrations.update_one({"_id": demo_id}, {"$set": {"approved": True}})
    worker.reconcile(db, provider, NOW)
    assert not provider.calls
    assert db.urgent_review_outbox.find_one({"demo_id": demo_id})["status"] == "watching"
    db.demonstrations.update_one({"_id": demo_id}, {"$set": {"approved": False}})
    worker.discover(db, CHAT, NOW)
    worker.reconcile(db, provider, NOW)
    assert len(provider.calls) == 1


def test_deleted_demo_updates_existing_message_without_exposing_retained_content(db):
    demo_id = _demo(db)
    provider = Provider()
    worker.discover(db, CHAT, NOW)
    worker.reconcile(db, provider, NOW)
    db.demonstrations.delete_one({"_id": demo_id})
    worker.reconcile(db, provider, NOW + timedelta(minutes=3))
    assert provider.calls[-1] == ("<b>Mielenosoitus poistettu</b>\nKäsittely päättynyt.", 123)
    worker.reconcile(db, provider, NOW + timedelta(minutes=6))
    assert len(provider.calls) == 2
    assert db.urgent_review_outbox.find_one({"demo_id": demo_id})["state"] == "deleted"


def test_rate_limit_waits_for_provider_deadline_then_retries_once(db):
    demo_id = _demo(db)
    provider = Provider([DeliveryFailure("rate_limited", retry_after=300)])
    worker.discover(db, CHAT, NOW)
    worker.reconcile(db, provider, NOW)
    job = db.urgent_review_outbox.find_one({"demo_id": demo_id})
    assert job["status"] == "retry"
    assert job["next_attempt_at"] == (NOW + timedelta(minutes=5)).replace(tzinfo=None)
    worker.reconcile(db, provider, NOW + timedelta(minutes=4))
    assert len(provider.calls) == 1
    db.demonstrations.update_one({"_id": demo_id}, {"$set": {"title": "Changed while waiting"}})
    worker.reconcile(db, provider, NOW + timedelta(minutes=5))
    assert len(provider.calls) == 2
    assert "Changed while waiting" in provider.calls[-1][0]
    assert db.urgent_review_outbox.find_one({"demo_id": demo_id})["message_id"] == 123


def test_uncertain_edit_forces_current_text_even_if_hash_reverts_to_last_receipt(db):
    demo_id = _demo(db)
    provider = Provider()
    worker.discover(db, CHAT, NOW)
    worker.reconcile(db, provider, NOW)
    original = provider.calls[0][0]
    db.demonstrations.update_one({"_id": demo_id}, {"$set": {"title": "Unconfirmed change"}})
    provider.failures.append(DeliveryFailure("unconfirmed_response", retry_after=60))
    worker.reconcile(db, provider, NOW + timedelta(minutes=3))
    db.demonstrations.update_one({"_id": demo_id}, {"$set": {"title": "Urgent review"}})
    worker.reconcile(db, provider, NOW + timedelta(minutes=6))
    assert provider.calls[-1] == (original, 123)
    assert len(provider.calls) == 3
    assert not db.urgent_review_outbox.find_one({"demo_id": demo_id}).get("needs_reconcile")


@pytest.mark.parametrize("uncertain,status", [(True, "delivery_unknown"), (False, "blocked")])
def test_unconfirmed_or_rejected_first_send_is_visible_and_never_blindly_replayed(db, uncertain, status):
    demo_id = _demo(db)
    provider = Provider([DeliveryFailure("sanitized_failure", uncertain=uncertain)])
    worker.discover(db, CHAT, NOW)
    worker.reconcile(db, provider, NOW)
    worker.discover(db, CHAT, NOW + timedelta(hours=1))
    worker.reconcile(db, provider, NOW + timedelta(hours=1))
    assert len(provider.calls) == 1
    job = db.urgent_review_outbox.find_one({"demo_id": demo_id})
    assert job["status"] == status
    assert job["error"] == "sanitized_failure"


@pytest.mark.parametrize("phase,message_id,status", [("claimed", None, "settled"), ("sending", None, "delivery_unknown"), ("sending", 123, "settled")])
def test_stale_claim_recovery_distinguishes_unknown_send_from_safe_edit(db, phase, message_id, status):
    demo_id = _demo(db)
    worker.discover(db, CHAT, NOW)
    change = {"status": "processing", "phase": phase, "claimed_at": NOW.replace(tzinfo=None) - worker.LEASE, "claim": "dead-worker"}
    if message_id:
        change["message_id"] = message_id
    db.urgent_review_outbox.update_one({"demo_id": demo_id}, {"$set": change})
    provider = Provider()
    worker.reconcile(db, provider, NOW)
    assert db.urgent_review_outbox.find_one({"demo_id": demo_id})["status"] == status
    if status == "delivery_unknown":
        assert not provider.calls
    else:
        assert len(provider.calls) == 1
        assert provider.calls[0][1] == message_id


def test_concurrent_workers_share_one_atomic_send_claim(db):
    _demo(db)
    worker.discover(db, CHAT, NOW)
    provider = Provider()
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(worker.reconcile, db, provider, NOW) for _ in range(2)]
        for future in futures:
            future.result(timeout=10)
    assert len(provider.calls) == 1


def test_delivery_batch_and_channel_scope_are_bounded(db, monkeypatch):
    for _ in range(3):
        _demo(db)
    worker.discover(db, CHAT, NOW)
    worker.discover(db, CHAT - 1, NOW)
    monkeypatch.setattr(worker, "DELIVERY_BATCH", 2)
    provider = Provider()
    worker.reconcile(db, provider, NOW)
    assert len(provider.calls) == 2
    assert db.urgent_review_outbox.count_documents({"chat_id": CHAT - 1, "message_id": {"$exists": True}}) == 0


def test_settled_history_cannot_consume_delivery_slots_and_future_reschedule_rearms(db, monkeypatch):
    first = _demo(db)
    provider = Provider()
    worker.discover(db, CHAT, NOW)
    worker.reconcile(db, provider, NOW)
    job = db.urgent_review_outbox.find_one({"demo_id": first})
    # Delivered historical rows retain their receipt but no longer poll forever.
    db.urgent_review_outbox.update_one({"_id": job["_id"]}, {"$set": {
        "observe_until": (NOW - timedelta(days=1)).replace(tzinfo=None),
    }})
    next_demo = _demo(db)
    monkeypatch.setattr(worker, "DELIVERY_BATCH", 1)
    worker.discover(db, CHAT, NOW + timedelta(minutes=3))
    worker.reconcile(db, provider, NOW + timedelta(minutes=3))
    assert db.urgent_review_outbox.find_one({"demo_id": first})["status"] == "done"
    assert db.urgent_review_outbox.find_one({"demo_id": next_demo})["message_id"] == 124
    db.demonstrations.update_one({"_id": first}, {"$set": {"title": "Rescheduled review"}})
    worker.discover(db, CHAT, NOW + timedelta(minutes=6))
    worker.reconcile(db, provider, NOW + timedelta(minutes=6))
    assert provider.calls[-1][1] == 123
    assert "Rescheduled review" in provider.calls[-1][0]


def test_settled_future_decision_is_still_updated_if_later_cancelled(db):
    demo_id = _demo(db)
    provider = Provider()
    worker.discover(db, CHAT, NOW)
    worker.reconcile(db, provider, NOW)
    db.demonstrations.update_one({"_id": demo_id}, {"$set": {"approved": True}})
    worker.reconcile(db, provider, NOW + timedelta(minutes=3))
    db.demonstrations.update_one({"_id": demo_id}, {"$set": {"cancelled": True}})
    worker.reconcile(db, provider, NOW + timedelta(minutes=6))
    assert "Peruttu" in provider.calls[-1][0]
    assert provider.calls[-1][1] == 123


def test_job_is_opt_in_and_registered_without_an_incoming_poller(app, db, monkeypatch):
    from mielenosoitukset_fi.background_jobs.definitions import JOB_DEFINITION_MAP
    assert JOB_DEFINITION_MAP["process_urgent_review_alerts"].default_trigger["trigger_args"]["minutes"] == 2
    calls = []
    monkeypatch.setattr(worker, "TelegramReviewTransport", lambda *args: calls.append(args) or Provider())
    with app.app_context():
        worker.run()
        assert not calls
        app.config["URGENT_REVIEW_TELEGRAM_ENABLED"] = True
        monkeypatch.setenv("URGENT_REVIEW_TELEGRAM_TOKEN", "123:test-fixture")
        monkeypatch.setenv("URGENT_REVIEW_TELEGRAM_CHAT_ID", str(CHAT))
        monkeypatch.setattr(worker.DatabaseManager, "get_instance", lambda: SimpleNamespace(get_db=lambda: db))
        worker.run()
        db.urgent_review_outbox.insert_one({"_id": "unknown-send", "chat_id": CHAT, "status": "delivery_unknown"})
        with pytest.raises(RuntimeError, match="operator reconciliation"):
            worker.run()
    assert calls == [("123:test-fixture", str(CHAT))] * 2


@pytest.mark.parametrize("message_id", [None, 321])
def test_telegram_adapter_returns_receipt_and_uses_only_expected_payload(monkeypatch, message_id):
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(status_code=200, json=lambda: {"ok": True, "result": {"message_id": 321}})
    monkeypatch.setattr(requests, "post", post)
    transport = TelegramReviewTransport("123:test-fixture", CHAT)
    assert transport.deliver("safe html", message_id) == 321
    url, kwargs = calls[0]
    assert url.endswith("/editMessageText" if message_id else "/sendMessage")
    assert kwargs["timeout"] == (5, 15)
    assert kwargs["allow_redirects"] is False
    assert kwargs["json"] == {"chat_id": CHAT, "text": "safe html", "parse_mode": "HTML", "link_preview_options": {"is_disabled": True}, **({"message_id": message_id} if message_id else {})}


@pytest.mark.parametrize("code,message_id,uncertain,retry", [(429, None, False, 300), (403, None, False, None), (500, None, True, 60), (500, 321, False, 60)])
def test_telegram_failures_have_sanitized_classification(monkeypatch, code, message_id, uncertain, retry):
    private = "must-not-persist-provider-body"
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: SimpleNamespace(status_code=code, json=lambda: {"ok": False, "error_code": code, "description": private, "parameters": {"retry_after": 300}}))
    with pytest.raises(DeliveryFailure) as caught:
        TelegramReviewTransport("123:test-fixture", CHAT).deliver("safe", message_id)
    assert private not in str(caught.value)
    assert caught.value.uncertain is uncertain
    assert caught.value.retry_after == retry


@pytest.mark.parametrize("message_id", [None, 321])
def test_telegram_timeout_never_exposes_secret_url_or_blindly_retries_send(monkeypatch, message_id):
    def fail(*args, **kwargs):
        raise requests.Timeout("https://api.telegram.org/bot123:secret-value/sendMessage")
    monkeypatch.setattr(requests, "post", fail)
    with pytest.raises(DeliveryFailure) as caught:
        TelegramReviewTransport("123:test-fixture", CHAT).deliver("safe", message_id)
    assert "secret-value" not in str(caught.value)
    assert caught.value.uncertain is (message_id is None)
    assert caught.value.retry_after == (60 if message_id is not None else None)


def test_telegram_unchanged_edit_and_invalid_receipt_are_not_new_sends(monkeypatch):
    transport = TelegramReviewTransport("123:test-fixture", CHAT)
    monkeypatch.setattr(requests, "post", lambda *a, **k: SimpleNamespace(status_code=400, json=lambda: {"ok": False, "error_code": 400, "description": "Bad Request: message is not modified"}))
    assert transport.deliver("safe", 321) == 321
    monkeypatch.setattr(requests, "post", lambda *a, **k: SimpleNamespace(status_code=200, json=lambda: {"ok": True, "result": {"message_id": True}}))
    with pytest.raises(DeliveryFailure) as caught:
        transport.deliver("safe")
    assert caught.value.uncertain is True
