from datetime import date, timedelta

from copy import deepcopy
from bson import ObjectId
import pytest
from urllib.parse import parse_qs, urlsplit


def test_public_demonstrations_list_uses_summary_payload(client, db, seeded_data):
    future_date = (date.today() + timedelta(days=7)).isoformat()
    db.demonstrations.update_one(
        {"_id": seeded_data["demo_id"]},
        {
            "$set": {
                "date": future_date,
                "large_internal_payload": "x" * 10000,
                "edit_history": [{"field": "title", "old": "A", "new": "B"}],
                "private_notes": "Not needed for the public list endpoint.",
            }
        },
    )

    response = client.get(
        "/api/demonstrations",
        query_string={"max_days_till": "60", "include_cancelled": "true"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["results"]

    demo = next(item for item in payload["results"] if item["_id"] == str(seeded_data["demo_id"]))
    assert demo["title"] == "Climate March Helsinki"
    assert demo["date"] == future_date
    assert demo["city"] == "Helsinki"
    assert demo["address"] == "Mannerheimintie 1, Helsinki"
    assert demo["cover_picture"] == "https://cdn.example.test/covers/demo.jpg"
    assert demo["preview_image"] == "https://cdn.example.test/previews/demo.jpg"
    assert demo["latitude"] == "60.1699"
    assert demo["longitude"] == "24.9384"

    assert "large_internal_payload" not in demo
    assert "edit_history" not in demo
    assert "private_notes" not in demo


def _pagination_demos(db, seeded_data):
    base = db.demonstrations.find_one({"_id": seeded_data["demo_id"]})
    records = []
    # Insertion order deliberately differs from chronological and ID order.
    for number, days, clock in [(6, 2, "09:00"), (5, 1, "18:00"), (4, 1, "10:00"),
                                (3, 1, "10:00"), (2, 1, "09:00"), (1, 1, "08:00")]:
        record = deepcopy(base)
        record.update(_id=ObjectId(f"{number:024x}"),
                      date=(date.today() + timedelta(days=days)).isoformat(),
                      start_time=clock, tags=["pagination-contract"])
        records.append(record)
    hidden = deepcopy(records[0])
    hidden.update(_id=ObjectId(), hide=True)
    db.demonstrations.insert_many(records + [hidden])
    return [str(record["_id"]) for record in sorted(
        records, key=lambda item: (item["date"], item["start_time"], item["_id"])
    )]


@pytest.mark.parametrize("endpoint,key", [
    ("/api/demonstrations", "results"), ("/api/v1/demonstrations", "demonstrations"),
])
def test_public_pages_have_chronological_tie_breaks_and_filtered_counts(client, db, seeded_data, endpoint, key):
    expected = _pagination_demos(db, seeded_data)
    actual = []
    for page in range(1, 4):
        response = client.get(endpoint, query_string={
            "tag": "pagination-contract", "city": "Helsinki", "page": page, "per_page": 2,
        })
        assert response.status_code == 200
        data = response.get_json()
        actual.extend(item["_id"] for item in data[key])
        assert data["total"] == 6  # hidden matching record is excluded
        assert data["page"] == page and data["per_page"] == 2
        assert data["total_pages"] == 3
        assert (data["result_start"], data["result_end"]) == (2 * page - 1, 2 * page)
        if key == "results":
            if page < 3:
                next_args = parse_qs(urlsplit(data["next_url"]).query)
                assert next_args == {"tag": ["pagination-contract"], "city": ["Helsinki"],
                                     "page": [str(page + 1)], "per_page": ["2"]}
            else:
                assert data["next_url"] is None
    assert actual == expected
    assert len(set(actual)) == len(expected)


@pytest.mark.parametrize("endpoint,key", [
    ("/api/demonstrations", "results"), ("/api/v1/demonstrations", "demonstrations"),
])
def test_public_page_metadata_handles_empty_and_out_of_range(client, db, seeded_data, endpoint, key):
    _pagination_demos(db, seeded_data)
    for tag, total in [("pagination-contract", 6), ("no-pagination-match", 0)]:
        response = client.get(endpoint, query_string={"tag": tag, "page": 9, "per_page": 2})
        assert response.status_code == 200
        data = response.get_json()
        assert data[key] == [] and data["total"] == total
        assert data["result_start"] == data["result_end"] == 0
        assert data["total_pages"] == max((total + 1) // 2, 1)


@pytest.mark.parametrize("endpoint", ["/api/demonstrations", "/api/v1/demonstrations"])
@pytest.mark.parametrize("args,expected", [
    ({"page": "bad", "per_page": "2"}, (1, 2)),
    ({"page": "2", "per_page": "bad"}, (2, 20)),
    ({"page": "-1", "per_page": "0"}, (1, 1)),
])
def test_public_pagination_normalizes_invalid_numeric_args(client, endpoint, args, expected):
    response = client.get(endpoint, query_string=args)
    assert response.status_code == 200
    data = response.get_json()
    assert (data["page"], data["per_page"]) == expected


def test_public_chronological_sort_has_index_backed_plan(app, db, seeded_data):
    from mielenosoitukset_fi.utils.database import DEMO_FILTER
    from mielenosoitukset_fi.utils.public_pagination import (
        PUBLIC_DEMONSTRATION_ORDER, PUBLIC_DEMONSTRATION_INDEX,
        ensure_public_demo_pagination_index,
    )

    indexes_before = db.demonstrations.index_information()
    ensure_public_demo_pagination_index(db)
    provisioned = db.demonstrations.index_information()
    ensure_public_demo_pagination_index(db)
    indexes_after = db.demonstrations.index_information()
    assert indexes_after == provisioned
    for name, specification in indexes_before.items():
        assert indexes_after[name] == specification
    assert indexes_after[PUBLIC_DEMONSTRATION_INDEX]['key'] == [('approved', 1), *PUBLIC_DEMONSTRATION_ORDER]

    base = db.demonstrations.find_one({"_id": seeded_data["demo_id"]})
    documents = []
    for index in range(200):
        item = deepcopy(base)
        item.update(_id=ObjectId(), date=(date.today() + timedelta(days=index % 8)).isoformat(),
                    start_time=f"{index % 24:02}:00")
        documents.append(item)
    db.demonstrations.insert_many(documents)
    query = deepcopy(DEMO_FILTER)
    query['date'] = {'$gte': date.today().isoformat()}
    def stages(node):
        if isinstance(node, dict):
            if 'stage' in node:
                yield node['stage']
            for value in node.values():
                yield from stages(value)
        elif isinstance(node, list):
            for value in node:
                yield from stages(value)

    for offset in [0, 12]:
        plan = db.demonstrations.find(query).sort(PUBLIC_DEMONSTRATION_ORDER).skip(offset).limit(12).explain()
        winning = plan['queryPlanner']['winningPlan']
        assert 'SORT' not in set(stages(winning)), winning
        assert 'IXSCAN' in set(stages(winning)), winning
        assert plan['executionStats']['nReturned'] == 12


def test_public_index_provisioning_is_not_part_of_route_import(monkeypatch):
    import ast
    from pathlib import Path
    from types import SimpleNamespace
    from mielenosoitukset_fi.scripts import provision_public_indexes

    source = ast.parse(Path('mielenosoitukset_fi/basic_routes.py').read_text())
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                   and node.func.id == 'ensure_public_demo_pagination_index'
                   for node in ast.walk(source))
    database = object()
    calls = []
    monkeypatch.setattr(provision_public_indexes, 'DatabaseManager', SimpleNamespace(
        get_instance=lambda: SimpleNamespace(get_db=lambda: database)))
    monkeypatch.setattr(provision_public_indexes, 'ensure_public_demo_pagination_index', calls.append)
    provision_public_indexes.main()
    assert calls == [database]
    script = Path('deploy/production_deploy.sh').read_text()
    assert script.index('python3 -m mielenosoitukset_fi.scripts.provision_public_indexes') < script.index('systemctl reload')
