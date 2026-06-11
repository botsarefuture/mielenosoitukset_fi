from mielenosoitukset_fi.utils.time_utils import utcnow
from datetime import datetime

from mielenosoitukset_fi.utils.logger import logger
from mielenosoitukset_fi.utils.migrations import migration_003_city_keys


MIGRATIONS = [
    {
        "id": "003_city_keys",
        "description": "Backfill normalized city keys for city-scoped admin grants.",
        "run": migration_003_city_keys.migrate_city_keys,
    },
]


def run_auto_migrations(db) -> None:
    """Run registered, idempotent migrations once per database."""
    applied = db.schema_migrations
    applied.create_index("id", unique=True)

    for migration in MIGRATIONS:
        migration_id = migration["id"]
        if applied.find_one({"id": migration_id}):
            continue

        logger.info("Running migration %s", migration_id)
        result = migration["run"](db=db)
        applied.insert_one(
            {
                "id": migration_id,
                "description": migration["description"],
                "applied_at": utcnow(),
                "result": result or {},
            }
        )
        logger.info("Migration %s completed", migration_id)
