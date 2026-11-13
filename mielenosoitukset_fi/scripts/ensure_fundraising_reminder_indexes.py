"""Create the unique e-mail index the Go signup route requires.

    python -m mielenosoitukset_fi.scripts.ensure_fundraising_reminder_indexes

Run it once per environment before enabling FUNDRAISING_REMINDER. In production
this needs the maintainer's go (docs/fundraising-reminder.md). Revert:
db.fundraising_reminders.dropIndex("email_unique").
"""
from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.fundraising_reminder import COLLECTION


def main(db=None):
    db = db if db is not None else DatabaseManager().get_instance().get_db()
    db[COLLECTION].create_index("email", unique=True, name="email_unique")
    db[COLLECTION].create_index("unsubscribe_hashes", name="unsubscribe_hashes")
    db[COLLECTION].create_index("confirm_hash", sparse=True, name="confirm_hash")
    return {"indexes": sorted(db[COLLECTION].index_information())}


if __name__ == "__main__":
    print(main())
