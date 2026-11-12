import io
import json
from datetime import date

from bson import ObjectId

from mielenosoitukset_fi.scripts import far_future_demos

TODAY = date(2026, 11, 10)


def _seed(db):
    db.demonstrations.delete_many({})
    db.recu_demos.delete_many({})
    parent_id, frozen_id = ObjectId(), ObjectId()
    db.recu_demos.insert_one({
        "_id": parent_id, "title": "Ilmastolakko", "freezed_children": [frozen_id],
        "created_until": "3100-01-05T00:00:00",
    })
    docs = [
        {"_id": ObjectId(), "title": "Ilmastolakko", "date": "3100-01-05", "parent": parent_id},
        {"_id": ObjectId(), "title": "Ilmastolakko", "date": "2094-05-01", "parent": str(parent_id)},
        {"_id": frozen_id, "title": "Ilmastolakko", "date": "2200-01-01", "parent": parent_id},
        {"_id": ObjectId(), "title": "Ilmastolakko", "date": "2027-03-01", "parent": parent_id},
        {"_id": ObjectId(), "title": "Käsin ilmoitettu", "date": "2150-01-01"},
        {"_id": ObjectId(), "title": "Outo päivä", "date": "ensi vuonna", "parent": parent_id},
    ]
    db.demonstrations.insert_many(docs)
    return parent_id, docs


def test_report_lists_only_generated_far_future_occurrences_and_changes_nothing(db):
    parent_id, docs = _seed(db)
    out = io.StringIO()

    assert far_future_demos.main([], db=db, today=TODAY, out=out) == 0

    text = out.getvalue()
    assert "Generated occurrences dated after 2028-11-10: 2" in text
    assert f"{parent_id}" in text and "2094-05-01 … 3100-01-05" in text
    assert "Report only; nothing was changed." in text
    assert db.demonstrations.count_documents({}) == len(docs)
    assert db.recu_demos.find_one({"_id": parent_id})["created_until"] == "3100-01-05T00:00:00"


def test_apply_refuses_a_count_that_was_not_reviewed(db, tmp_path):
    _, docs = _seed(db)
    backup = tmp_path / "backup.jsonl"
    out = io.StringIO()

    code = far_future_demos.main(
        ["--apply", "--backup", str(backup), "--expect", "5"], db=db, today=TODAY, out=out
    )

    assert code == 2
    assert "Refusing" in out.getvalue()
    assert not backup.exists()
    assert db.demonstrations.count_documents({}) == len(docs)


def test_apply_backs_up_then_deletes_and_resets_the_series(db, tmp_path):
    parent_id, docs = _seed(db)
    backup = tmp_path / "backup.jsonl"
    out = io.StringIO()

    code = far_future_demos.main(
        ["--apply", "--backup", str(backup), "--expect", "2"], db=db, today=TODAY, out=out
    )

    assert code == 0
    saved = [json.loads(line) for line in backup.read_text(encoding="utf-8").splitlines()]
    assert sorted(doc["date"] for doc in saved) == ["2094-05-01", "3100-01-05"]
    remaining = sorted(doc["date"] for doc in db.demonstrations.find({}, {"date": 1}))
    assert remaining == ["2027-03-01", "2150-01-01", "2200-01-01", "ensi vuonna"]
    # The watermark returns to the last stored occurrence inside the cutoff,
    # never to "today" and never to the kept frozen 2200 child.
    assert db.recu_demos.find_one({"_id": parent_id})["created_until"] == "2027-03-01T00:00:00"


def test_apply_keeps_the_series_anchor_when_only_near_events_remain(db, tmp_path):
    db.demonstrations.delete_many({})
    db.recu_demos.delete_many({})
    parent_id = ObjectId()
    db.recu_demos.insert_one({"_id": parent_id, "date": "2026-11-06", "created_until": "3100-01-01T00:00:00"})
    db.demonstrations.insert_many([
        {"_id": ObjectId(), "date": "2026-11-13", "parent": parent_id},
        {"_id": ObjectId(), "date": "2027-11-12", "parent": parent_id},
        {"_id": ObjectId(), "date": "2099-01-02", "parent": parent_id},
    ])

    code = far_future_demos.main(
        ["--apply", "--backup", str(tmp_path / "b.jsonl"), "--expect", "1"], db=db, today=TODAY, out=io.StringIO()
    )

    assert code == 0
    assert db.recu_demos.find_one({"_id": parent_id})["created_until"] == "2027-11-12T00:00:00"
    assert sorted(d["date"] for d in db.demonstrations.find()) == ["2026-11-13", "2027-11-12"]
