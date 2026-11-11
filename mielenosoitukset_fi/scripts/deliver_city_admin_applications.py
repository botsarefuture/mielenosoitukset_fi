"""Background job: turn Go-stored city admin applications into admin cases."""
from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.city_admin_applications import deliver_pending
from mielenosoitukset_fi.utils.logger import logger


def main(db=None):
    db = db if db is not None else DatabaseManager().get_instance().get_db()
    delivered = deliver_pending(db)
    if delivered:
        logger.info("Delivered %s city admin application(s) to cases", delivered)
    return {"delivered": delivered}
