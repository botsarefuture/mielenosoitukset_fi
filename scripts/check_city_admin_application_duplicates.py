#!/usr/bin/env python3
"""Read-only check: would the open-application unique index build?

Lists users with more than one open (received or in_review) city admin
application. Such users make `createIndex` fail. The script only runs an
aggregation; it never writes. Point it at a restored copy or run it deliberately
on production with the maintainer's approval.

Usage: python scripts/check_city_admin_application_duplicates.py
Exit code 0: no duplicates, 1: duplicates found.
"""
from __future__ import annotations

import sys

OPEN_STATUSES = ["received", "in_review"]

PIPELINE = [
    {"$match": {"status": {"$in": OPEN_STATUSES}}},
    {"$group": {"_id": "$user_id", "count": {"$sum": 1},
                "application_ids": {"$push": "$_id"}, "created": {"$push": "$created_at"}}},
    {"$match": {"count": {"$gt": 1}}},
    {"$sort": {"count": -1}},
]


def find_duplicates(db):
    return list(db.city_admin_applications.aggregate(PIPELINE))


def main() -> int:
    from mielenosoitukset_fi.database_manager import DatabaseManager

    duplicates = find_duplicates(DatabaseManager().get_instance().get_db())
    for row in duplicates:
        print(f"user {row['_id']}: {row['count']} open applications {row['application_ids']}")
    print(f"{len(duplicates)} user(s) with duplicate open applications")
    return 1 if duplicates else 0


if __name__ == "__main__":
    sys.exit(main())
