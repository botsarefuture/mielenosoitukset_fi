"""Report, and optionally remove, recurring occurrences generated far in the future (#1029).

A recurring series with a distant end date used to gain up to 1000 new
occurrences on every worker run, so the database holds events dated up to the
year 3100. The worker now stops one year ahead; this script deals with what was
already stored.

By default it only reports. Nothing is written unless ``--apply`` is given
together with a backup path and the exact number of documents the report
showed, so a run cannot remove more than was reviewed::

    python -m mielenosoitukset_fi.scripts.far_future_demos
    python -m mielenosoitukset_fi.scripts.far_future_demos --apply \
        --backup /root/far-future-demos.jsonl --expect 60123

Only documents that match all of these are candidates:

* ``date`` is a ``YYYY-MM-DD`` string later than today plus ``--years`` (default 2),
* the document has a ``parent`` (it is a generated occurrence, not a submission),
* its id is not in the parent's ``freezed_children`` (hand-edited occurrences stay).

After removal each affected series gets ``created_until`` moved back to its last
remaining occurrence (or its own date if none remain), so the worker keeps the
series' anchor and only generates what is missing within its horizon.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import date, datetime

from bson import ObjectId, json_util
from dateutil.relativedelta import relativedelta
from pymongo import MongoClient

from config import Config


def candidate_filter(cutoff: str) -> dict:
    return {
        "date": {"$type": "string", "$regex": r"^\d{4}-\d{2}-\d{2}$", "$gt": cutoff},
        "parent": {"$exists": True, "$ne": None},
    }


def find_candidates(db, cutoff: str) -> list[dict]:
    frozen: dict[str, set[str]] = {}
    candidates = []
    for doc in db.demonstrations.find(candidate_filter(cutoff)):
        parent_key = str(doc["parent"])
        if parent_key not in frozen:
            parent = None
            if ObjectId.is_valid(parent_key):
                parent = db.recu_demos.find_one({"_id": ObjectId(parent_key)}, {"freezed_children": 1})
            frozen[parent_key] = {str(value) for value in (parent or {}).get("freezed_children") or []}
        if str(doc["_id"]) not in frozen[parent_key]:
            candidates.append(doc)
    return candidates


def report(candidates: list[dict], cutoff: str, out=sys.stdout) -> None:
    print(f"Generated occurrences dated after {cutoff}: {len(candidates)}", file=out)
    by_parent = Counter(str(doc["parent"]) for doc in candidates)
    titles = {str(doc["parent"]): doc.get("title") for doc in candidates}
    print(f"Series affected: {len(by_parent)}", file=out)
    for parent, count in by_parent.most_common():
        dates = sorted(doc["date"] for doc in candidates if str(doc["parent"]) == parent)
        print(f"  {parent}  {count:>6}  {dates[0]} … {dates[-1]}  {titles[parent]!r}", file=out)
    by_decade = Counter(doc["date"][:3] + "0s" for doc in candidates)
    print("By decade: " + ", ".join(f"{decade} {count}" for decade, count in sorted(by_decade.items())), file=out)


def apply(db, candidates: list[dict], backup_path: str, today: date, cutoff: str) -> int:
    with open(backup_path, "x", encoding="utf-8") as backup:
        for doc in candidates:
            backup.write(json_util.dumps(doc) + "\n")
    ids = [doc["_id"] for doc in candidates]
    deleted = 0
    for start in range(0, len(ids), 1000):
        deleted += db.demonstrations.delete_many({"_id": {"$in": ids[start:start + 1000]}}).deleted_count
    for parent_key in {str(doc["parent"]) for doc in candidates}:
        if not ObjectId.is_valid(parent_key):
            continue
        parent_id = ObjectId(parent_key)
        # Move the watermark back to the last occurrence that is still stored,
        # never to today: the worker counts the schedule from this date and
        # deletes unfrozen children after it, so any other value would re-anchor
        # the series and touch events outside the reviewed set.
        remaining = db.demonstrations.find_one(
            {"parent": {"$in": [parent_id, parent_key]},
             "date": {"$type": "string", "$regex": r"^\d{4}-\d{2}-\d{2}$", "$lte": cutoff}},
            {"date": 1}, sort=[("date", -1)],
        )
        if remaining:
            watermark = remaining["date"]
        else:
            parent = db.recu_demos.find_one({"_id": parent_id}, {"date": 1}) or {}
            watermark = parent.get("date") if isinstance(parent.get("date"), str) else None
        if watermark:
            db.recu_demos.update_one(
                {"_id": parent_id}, {"$set": {"created_until": f"{watermark}T00:00:00"}}
            )
    return deleted


def main(argv: list[str] | None = None, db=None, today: date | None = None, out=sys.stdout) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--years", type=int, default=2, help="keep occurrences up to this many years ahead (default 2)")
    parser.add_argument("--apply", action="store_true", help="delete the reported documents")
    parser.add_argument("--backup", help="new JSON-lines file that receives every document before deletion")
    parser.add_argument("--expect", type=int, help="number of documents the reviewed report showed")
    args = parser.parse_args(argv)
    if args.years < 1:
        parser.error("--years must be at least 1")

    today = today or date.today()
    cutoff = (today + relativedelta(years=args.years)).isoformat()
    if db is None:
        db = MongoClient(Config.MONGO_URI)[Config.MONGO_DBNAME]
    candidates = find_candidates(db, cutoff)
    report(candidates, cutoff, out)

    if not args.apply:
        print("Report only; nothing was changed.", file=out)
        return 0
    if not args.backup or args.expect is None:
        parser.error("--apply needs --backup FILE and --expect COUNT")
    if args.expect != len(candidates):
        print(f"Refusing: --expect {args.expect} does not match the {len(candidates)} documents found.", file=out)
        return 2
    deleted = apply(db, candidates, args.backup, today, cutoff)
    print(f"Backed up {len(candidates)} documents to {args.backup}; deleted {deleted}.", file=out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
