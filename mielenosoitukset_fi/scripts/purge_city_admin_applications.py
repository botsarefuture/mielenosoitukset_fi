"""Background job: erase expired city admin application text (off by default)."""
from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.city_admin_applications import purge_expired, retention_enabled
from mielenosoitukset_fi.utils.logger import logger


def main(db=None):
    if not retention_enabled():
        return {"enabled": False, "purged": 0}
    db = db if db is not None else DatabaseManager().get_instance().get_db()
    purged = purge_expired(db)
    if purged:
        logger.info("Erased text of %s expired city admin application(s)", purged)
    return {"enabled": True, "purged": purged}
