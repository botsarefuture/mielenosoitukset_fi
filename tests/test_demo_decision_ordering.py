"""Deterministic interleavings against the real MongoDB decision boundary."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event, current_thread
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("first_decision", ["approved", "rejected"])
@pytest.mark.parametrize("pause_at", ["transition", "case_write", "case_cas"])
def test_later_opposite_decision_preserves_case_and_history_consistency(
    app, db, seeded_data, monkeypatch, first_decision, pause_at
):
    from mielenosoitukset_fi.demonstrations import decisions

    paused, resume = Event(), Event()
    demo_id = seeded_data["pending_demo_id"]
    second_decision = "rejected" if first_decision == "approved" else "approved"
    queued = []
    sender = SimpleNamespace(queue_email=lambda **kwargs: queued.append(kwargs))

    def gate():
        if current_thread().name.startswith("first-decision"):
            paused.set()
            assert resume.wait(10), "second decision did not release first request"

    if pause_at == "transition":
        collection_type = type(db.demonstrations)
        original = collection_type.find_one_and_update

        def transition(collection, query, *args, **kwargs):
            result = original(collection, query, *args, **kwargs)
            if collection.name == "demonstrations" and query.get("_id") == demo_id:
                gate()
            return result

        monkeypatch.setattr(collection_type, "find_one_and_update", transition)
    elif pause_at == "case_write":
        original = decisions._close_related_cases

        def close_cases(*args, **kwargs):
            gate()
            return original(*args, **kwargs)

        monkeypatch.setattr(decisions, "_close_related_cases", close_cases)
    else:
        collection_type = type(db.cases)
        original = collection_type.update_one

        def update_case(collection, query, *args, **kwargs):
            if collection.name == "cases" and query.get("_id") == seeded_data["case_id"]:
                gate()
            return original(collection, query, *args, **kwargs)

        monkeypatch.setattr(collection_type, "update_one", update_case)

    def decide(status, actor):
        with app.app_context():
            return decisions.apply_demo_decision(
                db, demo_id, status, actor={"username": actor}, source=actor,
                email_sender=sender, public_url=f"https://example.test/demonstration/{demo_id}",
            )

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="first-decision") as pool:
        first = pool.submit(decide, first_decision, "first-reviewer")
        try:
            assert paused.wait(10), "first decision did not reach the requested boundary"
            second = decide(second_decision, "second-reviewer")
        finally:
            resume.set()
        first_result = first.result(timeout=10)

    final = db.demonstrations.find_one({"_id": demo_id})
    case = db.cases.find_one({"_id": seeded_data["case_id"]})
    assert final["moderation_decision"]["id"] == second.decision_id
    assert final["moderation_decision"]["status"] == second_decision
    assert case["outcome"] == case["resolution"] == second_decision
    assert case["meta"]["decision_id"] == second.decision_id
    for result, status in [(first_result, first_decision), (second, second_decision)]:
        assert result.changed is True
        assert result.demo["moderation_decision"]["id"] == result.decision_id
        assert result.demo["approved"] is (status == "approved")
        assert result.demo["rejected"] is (status == "rejected")
        histories = list(db.demo_edit_history.find({
            "demo_id": str(demo_id),
            "new_demo.moderation_decision.id": result.decision_id,
        }))
        assert len(histories) == 1
        assert histories[0]["new_demo"]["approved"] is (status == "approved")
        assert histories[0]["new_demo"]["rejected"] is (status == "rejected")


@pytest.mark.parametrize("first_decision", ["approved", "rejected"])
def test_current_decision_retries_case_compare_and_set_after_an_older_writer(
    app, db, seeded_data, monkeypatch, first_decision
):
    from mielenosoitukset_fi.demonstrations import decisions

    second_decision = "rejected" if first_decision == "approved" else "approved"
    ready = {status: Event() for status in [first_decision, second_decision]}
    allowed = {status: Event() for status in [first_decision, second_decision]}
    calls = {status: 0 for status in [first_decision, second_decision]}
    collection_type = type(db.cases)
    original = collection_type.update_one

    def update_case(collection, query, update, *args, **kwargs):
        if collection.name == "cases" and query.get("_id") == seeded_data["case_id"]:
            status = update["$set"]["outcome"]
            calls[status] += 1
            ready[status].set()
            assert allowed[status].wait(10), "case writer not released"
        return original(collection, query, update, *args, **kwargs)

    monkeypatch.setattr(collection_type, "update_one", update_case)
    sender = SimpleNamespace(queue_email=lambda **kwargs: None)

    def decide(status):
        with app.app_context():
            return decisions.apply_demo_decision(
                db, seeded_data["pending_demo_id"], status,
                actor={"username": status}, source="case-cas-test", email_sender=sender,
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(decide, first_decision)
        try:
            assert ready[first_decision].wait(10)
            second = pool.submit(decide, second_decision)
            assert ready[second_decision].wait(10)
            allowed[first_decision].set()
            first_result = first.result(timeout=10)
            allowed[second_decision].set()
            second_result = second.result(timeout=10)
        finally:
            for event in allowed.values():
                event.set()

    assert calls == {first_decision: 1, second_decision: 2}
    case = db.cases.find_one({"_id": seeded_data["case_id"]})
    assert case["outcome"] == case["resolution"] == second_decision
    assert case["meta"]["decision_id"] == second_result.decision_id
    entries = [entry["metadata"]["decision_id"] for entry in case["case_history"]
               if "decision_id" in entry.get("metadata", {})]
    assert entries == [first_result.decision_id, second_result.decision_id]


@pytest.mark.parametrize("status", ["approved", "rejected"])
def test_overlapping_same_decision_keeps_one_history_and_notification(
    app, db, seeded_data, monkeypatch, status
):
    from mielenosoitukset_fi.demonstrations import decisions

    paused, resume = Event(), Event()
    demo_id = seeded_data["pending_demo_id"]
    collection_type = type(db.demonstrations)
    original = collection_type.find_one_and_update
    queued = []
    sender = SimpleNamespace(queue_email=lambda **kwargs: queued.append(kwargs))

    def transition(collection, query, *args, **kwargs):
        result = original(collection, query, *args, **kwargs)
        if (collection.name == "demonstrations" and query.get("_id") == demo_id
                and current_thread().name.startswith("first-decision")):
            paused.set()
            assert resume.wait(10)
        return result

    monkeypatch.setattr(collection_type, "find_one_and_update", transition)

    def decide():
        with app.app_context():
            return decisions.apply_demo_decision(
                db, demo_id, status, actor={"username": "reviewer"},
                source="same-decision-test", email_sender=sender,
            )

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="first-decision") as pool:
        first = pool.submit(decide)
        try:
            assert paused.wait(10)
            second = decide()
        finally:
            resume.set()
        first_result = first.result(timeout=10)

    assert first_result.changed is True and second.changed is False
    assert first_result.decision_id == second.decision_id
    assert len(queued) == 1
    assert db.demo_decision_notifications.count_documents({"decision_id": second.decision_id}) == 1
    assert db.demo_edit_history.count_documents({
        "demo_id": str(demo_id), "new_demo.moderation_decision.id": second.decision_id,
    }) == 1
    assert db.demo_audit_logs.count_documents({
        "demo_id": str(demo_id), "details.decision_id": second.decision_id,
        "action": "approve_demo" if status == "approved" else "reject_demo",
    }) == 1
    case = db.cases.find_one({"_id": seeded_data["case_id"]})
    assert case["outcome"] == case["resolution"] == status
    assert sum(entry.get("metadata", {}).get("decision_id") == second.decision_id
               for entry in case["case_history"]) == 1


@pytest.mark.parametrize("initial_status", ["approved", "rejected"])
def test_unchanged_request_retries_the_actual_newer_decision_notification(
    app, db, seeded_data, monkeypatch, initial_status
):
    from mielenosoitukset_fi.demonstrations import decisions

    demo_id = seeded_data["pending_demo_id"]
    newer_status = "rejected" if initial_status == "approved" else "approved"
    paused, resume = Event(), Event()
    attempts = []

    def flaky_email(**kwargs):
        attempts.append(kwargs)
        if len(attempts) == 1:
            raise RuntimeError("first newer-decision enqueue fails")

    def decide(status, sender):
        with app.app_context():
            return decisions.apply_demo_decision(
                db, demo_id, status, actor={"username": "reviewer"},
                source="unchanged-interleaving-test", email_sender=sender,
            )

    decide(initial_status, SimpleNamespace(queue_email=lambda **kwargs: None))
    collection_type = type(db.demonstrations)
    original = collection_type.find_one_and_update

    def transition(collection, query, *args, **kwargs):
        result = original(collection, query, *args, **kwargs)
        if (collection.name == "demonstrations" and query.get("_id") == demo_id
                and current_thread().name.startswith("first-decision")):
            assert result is None  # This request observed an unchanged state.
            paused.set()
            assert resume.wait(10)
        return result

    monkeypatch.setattr(collection_type, "find_one_and_update", transition)
    sender = SimpleNamespace(queue_email=flaky_email)
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="first-decision") as pool:
        first = pool.submit(decide, initial_status, sender)
        try:
            assert paused.wait(10)
            with pytest.raises(RuntimeError, match="enqueue fails"):
                decide(newer_status, sender)
        finally:
            resume.set()
        result = first.result(timeout=10)

    final = db.demonstrations.find_one({"_id": demo_id})
    assert result.changed is False
    assert result.decision_id == final["moderation_decision"]["id"]
    assert result.demo["approved"] is (newer_status == "approved")
    assert result.demo["rejected"] is (newer_status == "rejected")
    assert [attempt["template_name"] for attempt in attempts] == [
        f"demo_submitter_{newer_status}.html",
        f"demo_submitter_{newer_status}.html",
    ]
    case = db.cases.find_one({"_id": seeded_data["case_id"]})
    assert case["outcome"] == case["resolution"] == newer_status
    assert case["meta"]["decision_id"] == result.decision_id
