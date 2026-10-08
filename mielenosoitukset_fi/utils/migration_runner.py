from mielenosoitukset_fi.utils.time_utils import utcnow
from datetime import datetime

from mielenosoitukset_fi.utils.logger import logger
from mielenosoitukset_fi.utils.migrations import (
    migration_003_city_keys,
    migration_004_admin_governance,
    migration_005_user_identity_uniqueness,
    migration_006_passkeys,
    migration_007_site_analytics,
    migration_008_visitor_analytics,
    migration_009_fresh_step_up,
    migration_010_web_vitals,
)


MIGRATIONS = [
    {
        "id": "003_city_keys",
        "description": "Backfill normalized city keys for city-scoped admin grants.",
        "run": migration_003_city_keys.migrate_city_keys,
    },
    {
        "id": "004_admin_governance",
        "description": "Persist board clearances and add explicit city-management access.",
        "run": migration_004_admin_governance.migrate_admin_governance,
    },
    {
        "id": "005_user_identity_uniqueness",
        "description": "Enforce case-insensitive username and email uniqueness.",
        "run": migration_005_user_identity_uniqueness.migrate_user_identity_uniqueness,
    },
    {
        "id": "006_passkey_storage",
        "description": "Add storage and indexes for WebAuthn passkeys and challenges.",
        "run": migration_006_passkeys.migrate_passkey_storage,
    },
    {
        "id": "007_site_analytics",
        "description": "Add indexes for built-in first-party site analytics counters.",
        "run": migration_007_site_analytics.migrate_site_analytics,
    },
    {
        "id": "008_visitor_analytics",
        "description": "Add indexes and retention for anonymous distinct-visitor counting.",
        "run": migration_008_visitor_analytics.migrate_visitor_analytics,
    },
    {
        "id": "009_fresh_step_up",
        "description": "Add storage and indexes for fresh step-up tokens.",
        "run": migration_009_fresh_step_up.migrate_fresh_step_up_storage,
    },
    {
        "id": "010_web_vitals",
        "description": "Add bounded daily histograms for anonymous Web Vitals.",
        "run": migration_010_web_vitals.migrate_web_vitals,
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
