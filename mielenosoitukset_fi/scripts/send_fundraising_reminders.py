"""Background job and command: the one fundraising opening reminder.

    python -m mielenosoitukset_fi.scripts.send_fundraising_reminders --dry-run

lists how many would be sent and sends nothing. A real run needs
FUNDRAISING_REMINDER_MAILS_ENABLED and FUNDRAISING_REMINDER_BULK_SEND_APPROVED,
and only works from 16.11.2026 00:00 Helsinki for one day.
"""
import argparse
import json

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.fundraising_reminder import send_reminders
from mielenosoitukset_fi.utils.logger import logger


def main(db=None, dry_run=False):
    db = db if db is not None else DatabaseManager().get_instance().get_db()
    result = send_reminders(db, dry_run=dry_run)
    if result.get("sent"):
        logger.info("Queued %s fundraising reminder(s)", result["sent"])
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="count only, send nothing")
    print(json.dumps(main(dry_run=parser.parse_args().dry_run), default=str))
