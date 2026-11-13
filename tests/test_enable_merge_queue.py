from copy import deepcopy

import pytest

from scripts import enable_merge_queue as queue


@pytest.fixture
def ruleset():
    return {
        "id": 1440033, "name": "Protection", "target": "branch",
        "enforcement": "active",
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "bypass_actors": [{"actor_id": 1, "actor_type": "Integration", "bypass_mode": "pull_request"}],
        "rules": [
            {"type": "deletion"}, {"type": "creation"},
            {"type": "pull_request", "parameters": {"required_approving_review_count": 1}},
            {"type": "copilot_code_review", "parameters": {}},
            {"type": "required_status_checks", "parameters": {
                "required_status_checks": [{"context": "python-tests", "integration_id": 1}],
                "strict_required_status_checks_policy": True,
            }},
            queue.queue_rule({**queue.QUEUE_PARAMETERS, "max_entries_to_build": 3, "max_entries_to_merge": 3}),
        ],
    }


def test_resize_preserves_every_other_protection_and_input(ruleset):
    before = deepcopy(ruleset)
    payload = queue.payload_for(ruleset)
    assert ruleset == before
    assert payload["rules"][:-1] == before["rules"][:-1]
    for key in ("conditions", "bypass_actors", "name", "target", "enforcement"):
        assert payload[key] == before[key]
    assert payload["rules"][-1] == queue.queue_rule()
    assert queue.payload_for(payload) == payload
    rollback = {**queue.QUEUE_PARAMETERS, "max_entries_to_build": 3, "max_entries_to_merge": 3}
    assert queue.payload_for(payload, rollback)["rules"] == before["rules"]


def test_adds_only_one_queue_when_missing(ruleset):
    ruleset["rules"].pop()
    payload = queue.payload_for(ruleset)
    assert payload["rules"][:-1] == ruleset["rules"]
    assert len(queue.payload_for(payload)["rules"]) == 6


def test_matching_confirm_does_not_write(monkeypatch, ruleset):
    ruleset = {**ruleset, "rules": queue.payload_for(ruleset)["rules"]}
    monkeypatch.setattr(queue, "check_repository", lambda: {})
    monkeypatch.setattr(queue, "check_workflow", lambda: None)
    monkeypatch.setattr(queue, "check_recent_checks", lambda: "ok")
    monkeypatch.setattr(queue, "ruleset_candidates", lambda: [ruleset])
    monkeypatch.setattr(queue, "apply", lambda *args: pytest.fail("unexpected write"))
    assert queue.main(["--confirm"]) == 0


def test_requires_explicit_mode():
    assert queue.main([]) == 2


def test_verification_detects_other_protection_changes(monkeypatch, ruleset):
    expected = queue.payload_for(ruleset)
    returned = deepcopy(expected)
    returned["rules"][2]["parameters"]["required_approving_review_count"] = 0
    monkeypatch.setattr(queue, "get_json", lambda _: returned)
    with pytest.raises(queue.ScriptError, match="differs"):
        queue.verify(1440033, expected)
