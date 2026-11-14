"""Print the confirmed Pride banner carriers as CSV (read-only).

    python -m mielenosoitukset_fi.scripts.export_pride_banner_volunteers > carriers.csv

The output holds personal data: keep the file private and delete it after use.
"""
from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.pride_banner_volunteers import export_confirmed


def main(db=None):
    db = db if db is not None else DatabaseManager().get_instance().get_db()
    return export_confirmed(db)


if __name__ == "__main__":
    print(main(), end="")
