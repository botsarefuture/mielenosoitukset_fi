"""Acknowledged support reply receipts using real Mongo, never SMTP."""

import importlib
import logging
from unittest.mock import Mock

import pytest
from jinja2 import Environment, FileSystemLoader
from pymongo.collection import Collection
from pymongo.results import InsertOneResult, UpdateResult

from mielenosoitukset_fi.emailer.EmailSender import EmailSender


QUEUE_EMAIL = EmailSender.queue_email


@pytest.fixture
def reply_sender(monkeypatch, db, app, admin_client, seeded_data):
    module = importlib.import_module(app.view_functions["admin_case.reply_to_ticket"].__module__)
    sender = object.__new__(EmailSender)
    sender._env = Environment(loader=FileSystemLoader("mielenosoitukset_fi/templates/emails"))
    sender._queue_collection = db.email_queue
    sender._instance_id = "support-reply-test"
    sender._logger = logging.getLogger(__name__)
    sender._start_retry_timer = Mock()
    sender.queue_email = QUEUE_EMAIL.__get__(sender, EmailSender)
    monkeypatch.setattr(module, "email_sender", sender)
    db.cases.update_one({"_id": seeded_data["case_id"]}, {"$set": {
        "type": "support_ticket",
        "submitter": {"submitter_email": "recipient@example.test"},
        "meta.ticket.message_id": "<original@example.test>",
    }})
    return sender


def _reply(client, case_id):
    response = client.post(f"/admin/case/{case_id}/reply/", data={"reply_message": "**Vastaus**"})
    assert response.status_code == 302
    with client.session_transaction() as session:
        return session.get("_flashes", [])


def _unconfirmed(flashes):
    assert any(category == "warning" and "ei voitu vahvistaa" in text for category, text in flashes)
    assert any("Älä lähetä vastausta uudelleen" in text for _, text in flashes)
    assert not any(category == "success" or "private diagnostic" in text for category, text in flashes)


def test_acknowledged_reply_has_one_correlated_atomic_receipt(reply_sender, admin_client, db, seeded_data, monkeypatch):
    case_id = seeded_data["case_id"]
    before = db.cases.find_one({"_id": case_id})
    original_update = Collection.update_one
    writes = []

    def inspect_update(collection, query, update, *args, **kwargs):
        if collection.full_name == db.cases.full_name:
            assert db.email_queue.count_documents({}) == 1
            assert db.cases.find_one({"_id": case_id}) == before
            writes.append(update)
        return original_update(collection, query, update, *args, **kwargs)

    monkeypatch.setattr(Collection, "update_one", inspect_update)
    flashes = _reply(admin_client, case_id)
    assert any(category == "success" and "Toimitusta ei ole vielä vahvistettu" in text for category, text in flashes)
    case = db.cases.find_one({"_id": case_id})
    assert len(writes) == 1
    assert db.email_queue.count_documents({}) == 1
    job = db.email_queue.find_one({})
    reply = case["suggestion"]["messages"][-1]
    history = case["case_history"][-1]
    action = case["action_logs"][-1]
    assert len(case["suggestion"]["messages"]) == len(before["suggestion"].get("messages", [])) + 1
    assert len(case["case_history"]) == len(before.get("case_history", [])) + 1
    assert len(case["action_logs"]) == len(before.get("action_logs", [])) + 1
    assert reply["status"] == "queued" and reply["message"] == "**Vastaus**"
    assert reply["message_id"] == job["extra_headers"]["Message-ID"]
    assert job["extra_headers"]["In-Reply-To"] == "<original@example.test>"
    assert reply["message_id"] in case["meta"]["ticket"]["reply_message_ids"]
    assert history["action"] == "Vastaus lisätty lähetysjonoon."
    for field in before.keys() - {"suggestion", "meta", "updated_at", "case_history", "action_logs"}:
        assert case[field] == before[field]
    for receipt in (reply, history["metadata"], action):
        assert receipt["queue_id"] == job["_id"]
        assert receipt["message_id"] == reply["message_id"]
    reply_sender._start_retry_timer.assert_not_called()


@pytest.mark.parametrize("failure", ["render", "before_insert", "after_insert", "unacknowledged"])
def test_queue_failure_is_unconfirmed_without_case_writes_or_retries(reply_sender, admin_client, db, seeded_data, monkeypatch, failure):
    case_id = seeded_data["case_id"]
    before = db.cases.find_one({"_id": case_id})
    original_insert = Collection.insert_one
    if failure == "render":
        monkeypatch.setattr(reply_sender._env, "get_template", Mock(side_effect=RuntimeError("private diagnostic")))

    def fail_insert(collection, document, *args, **kwargs):
        if collection.full_name != db.email_queue.full_name:
            return original_insert(collection, document, *args, **kwargs)
        if failure == "before_insert":
            raise RuntimeError("private diagnostic")
        result = original_insert(collection, document, *args, **kwargs)
        if failure == "after_insert":
            raise RuntimeError("private diagnostic")
        return InsertOneResult(result.inserted_id, acknowledged=False)

    monkeypatch.setattr(Collection, "insert_one", fail_insert)
    _unconfirmed(_reply(admin_client, case_id))
    assert db.cases.find_one({"_id": case_id}) == before
    assert db.email_queue.count_documents({}) == (0 if failure in ("render", "before_insert") else 1)
    reply_sender._start_retry_timer.assert_not_called()


@pytest.mark.parametrize("failure", ["before_write", "after_write", "unacknowledged", "unmatched"])
def test_case_receipt_failure_is_unconfirmed_without_retrying_queue(reply_sender, admin_client, db, seeded_data, monkeypatch, failure):
    case_id = seeded_data["case_id"]
    before = db.cases.find_one({"_id": case_id})
    original_update = Collection.update_one

    def fail_update(collection, query, update, *args, **kwargs):
        if collection.full_name != db.cases.full_name:
            return original_update(collection, query, update, *args, **kwargs)
        if failure == "before_write":
            raise RuntimeError("private diagnostic")
        if failure == "unmatched":
            return UpdateResult({"n": 0, "nModified": 0}, acknowledged=True)
        original_update(collection, query, update, *args, **kwargs)
        if failure == "after_write":
            raise RuntimeError("private diagnostic")
        return UpdateResult(None, acknowledged=False)

    monkeypatch.setattr(Collection, "update_one", fail_update)
    _unconfirmed(_reply(admin_client, case_id))
    assert db.email_queue.count_documents({}) == 1
    if failure in ("before_write", "unmatched"):
        assert db.cases.find_one({"_id": case_id}) == before
    else:
        assert db.cases.find_one({"_id": case_id})["suggestion"]["messages"][-1]["status"] == "queued"
    reply_sender._start_retry_timer.assert_not_called()


def test_legacy_queue_success_still_returns_none(reply_sender, db):
    assert reply_sender.queue_email(
        "customer_support/ticket_admin_reply.html", "Test", ["recipient@example.test"], {},
    ) is None
    assert db.email_queue.count_documents({}) == 1
    reply_sender._start_retry_timer.assert_not_called()


def test_legacy_queue_retries_keep_their_contract(reply_sender, db, monkeypatch):
    original_insert = Collection.insert_one
    attempts = []

    def fail_insert(collection, document, *args, **kwargs):
        if collection.full_name == db.email_queue.full_name:
            attempts.append(document)
            raise RuntimeError("private diagnostic")
        return original_insert(collection, document, *args, **kwargs)

    monkeypatch.setattr(Collection, "insert_one", fail_insert)
    assert reply_sender.queue_email(
        "customer_support/ticket_admin_reply.html", "Test", ["recipient@example.test"], {},
    ) is None
    for attempt in (1, 2):
        delay, callback, arguments = reply_sender._start_retry_timer.call_args.args
        assert delay == 3600 and arguments == [attempt]
        callback(*arguments)
    assert len(attempts) == 3
    assert reply_sender._start_retry_timer.call_count == 2
    assert db.email_queue.count_documents({}) == 0
