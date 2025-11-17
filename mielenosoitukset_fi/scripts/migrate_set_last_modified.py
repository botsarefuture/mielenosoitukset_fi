#!/usr/bin/env python3
"""
Migration script: set `last_modified` to the moment the migration is run for all demonstrations.

Run from repository root:

    python3 mielenosoitukset_fi/scripts/migrate_set_last_modified.py

"""
from datetime import datetime

from mielenosoitukset_fi.utils.logger import logger
from mielenosoitukset_fi.utils.database import get_database_manager


def main():
    db = get_database_manager()
    now = datetime.utcnow()

    # Update all documents in the `demonstrations` collection
    result = db["demonstrations"].update_many({}, {"$set": {"last_modified": now}})

    logger.info(
        "migrate_set_last_modified: matched=%d modified=%d set_last_modified=%s",
        result.matched_count,
        result.modified_count,
        now.isoformat(),
    )

    print(
        f"migrate_set_last_modified: matched={result.matched_count} modified={result.modified_count} last_modified={now.isoformat()}"
    )


if __name__ == "__main__":
    main()
