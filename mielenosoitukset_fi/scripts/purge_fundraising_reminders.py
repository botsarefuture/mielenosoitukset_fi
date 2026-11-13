"""Background job and command: erase expired fundraising reminder data.

    python -m mielenosoitukset_fi.scripts.purge_fundraising_reminders --dry-run
"""
import argparse
import json

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.fundraising_reminder import purge
from mielenosoitukset_fi.utils.logger import logger


def main(db=None, dry_run=False):
    db = db if db is not None else DatabaseManager().get_instance().get_db()
    result = purge(db, dry_run=dry_run)
    if not dry_run and (result["pending_expired"] or result["retention_ended"]):
        logger.info("Purged fundraising reminder data: %s", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="count only, delete nothing")
    print(json.dumps(main(dry_run=parser.parse_args().dry_run), default=str))
