from mielenosoitukset_fi.utils.time_utils import utcnow

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


class PendingMigrationsError(RuntimeError):
    def __init__(self, pending_ids):
        self.pending_ids = list(pending_ids)
        super().__init__("Pending migrations: " + ", ".join(self.pending_ids))


class MigrationApprovalError(ValueError):
    pass


def pending_migrations(db) -> list[str]:
    """Read missing registered IDs without creating indexes or changing data."""
    return [
        migration["id"]
        for migration in MIGRATIONS
        if not db.schema_migrations.find_one({"id": migration["id"]})
    ]


def assert_migrations_ready(db) -> None:
    pending = pending_migrations(db)
    if pending:
        raise PendingMigrationsError(pending)


def run_approved_migrations(db, approved_ids) -> list[str]:
    """Apply approved pending migrations while the caller holds the deploy lock.

    Validate the entire pending set before any index or data write. Already
    applied registered IDs may remain approved when retrying a deployment.
    """
    approved = set(approved_ids)
    registered = {migration["id"] for migration in MIGRATIONS}
    if approved - registered:
        raise MigrationApprovalError("Approval contains an unregistered migration ID.")
    pending = pending_migrations(db)
    unapproved = [migration_id for migration_id in pending if migration_id not in approved]
    if unapproved:
        raise PendingMigrationsError(unapproved)
    if not pending:
        return []
    return _run_migrations(db, [migration for migration in MIGRATIONS if migration["id"] in pending])


def run_auto_migrations(db) -> None:
    """Run registered, idempotent migrations once per database (legacy/manual)."""
    _run_migrations(db, MIGRATIONS)


def _run_migrations(db, migrations) -> list[str]:
    applied = db.schema_migrations
    applied.create_index("id", unique=True)
    completed = []

    for migration in migrations:
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
        completed.append(migration_id)
        logger.info("Migration %s completed", migration_id)
    return completed
