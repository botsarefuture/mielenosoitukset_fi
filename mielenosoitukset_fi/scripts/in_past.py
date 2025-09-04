"""
Copyright
---------
Verso Vuorenmaa 2024

Description
-----------
This script is responsible for marking past demonstrations in the database.
Instead of hiding them, starting from v4.3.2, past demonstrations are flagged
with the attribute ``in_past = True``.

Modules
-------
datetime : Provides classes for manipulating dates and times.
importlib : Provides the implementation of the import statement.
os : Provides a way of using operating system dependent functionality.
sys : Provides access to variables used or maintained by the interpreter.

Functions
---------
is_future_demo(demo_date, today)
    Check if the given demonstration date is in the future compared to today's date.

fetch_upcoming_demos(_tr=False)
    Fetch upcoming demonstrations from the database that are not in the past.

hide_past_demos(demos, today)
    Iterate through the list of demonstrations and mark those that are in the past.

hide_past(_tr=False)
    Main function that marks past demonstrations as in_past by fetching the
    upcoming demonstrations and processing them.

Usage
-----
This script is intended to be run as a standalone module. When executed, it will
mark past demonstrations as in_past in the database.

Version History
---------------
v2.4.0
    Added the ability to hide past demonstrations in the database.
v4.3.2
    Changed logic to mark demonstrations as ``in_past`` instead of hiding them.
    Improved statistics reporting and docstrings to Numpydoc style.
"""

import importlib
import os
import sys
from datetime import datetime

# Get the parent directory
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_dir)

# Import necessary modules
classes = importlib.import_module("utils.classes")
database_manager = importlib.import_module("database_manager")
if __name__ == "__main__":
    app = importlib.import_module("app").create_app()
variables = importlib.import_module("utils.variables")

# Get the database instance
DatabaseManager = database_manager.DatabaseManager
Demonstration = classes.Demonstration
RecurringDemonstration = classes.RecurringDemonstration
db_manager = DatabaseManager().get_instance()
db = db_manager.get_db()


def is_future_demo(demo_date, today):
    """Check if the demonstration is in the future.

    Parameters
    ----------
    demo_date : datetime.date
        The date of the demonstration.
    today : datetime.date
        The current date.

    Returns
    -------
    bool
        True if the demonstration date is today or later, False otherwise.
    """
    return demo_date >= today


def fetch_upcoming_demos(_tr: bool = False):
    """Fetch upcoming demonstrations that are not in the past.

    Parameters
    ----------
    _tr : bool, optional
        If True, fetch all demonstrations regardless of date (default is False).

    Returns
    -------
    list of dict
        List of demonstration documents.
    """
    if _tr:
        return list(db["demonstrations"].find())
    return list(db["demonstrations"].find(variables.DEMO_FILTER))


def hide_past_demos(demos, today):
    """Mark past demonstrations with the attribute ``in_past = True``.

    Parameters
    ----------
    demos : list of dict
        A list of demonstrations with at least a 'date' key.
    today : datetime.date
        The current date used for comparison.

    Returns
    -------
    dict
        Dictionary with statistics: total processed, marked as past, and errors.

    Notes
    -----
    - Prior to v4.3.2, past demonstrations were hidden (``hide = True``).
    - Since v4.3.2, past demonstrations are kept visible but flagged as past.
    """
    stats = {"total": 0, "hidden": 0, "errors": 0}

    for demo in demos:
        stats["total"] += 1
        try:
            demo_date = datetime.strptime(demo["date"], "%Y-%m-%d").date()
            if not is_future_demo(demo_date, today):
                try:
                    demonstration_instance = Demonstration.from_dict(demo)
                except Exception:
                    demonstration_instance = RecurringDemonstration.from_dict(demo)
                demonstration_instance.in_past = True

                # CHANGE v4.3.2: Do not hide, just mark as in_past
                demonstration_instance.save()
                stats["hidden"] += 1
        except Exception as e:
            stats["errors"] += 1
            print(f"Error processing demonstration {demo['_id']}: {e}")

    return stats


def hide_past(_tr: bool = False):
    """Main function to mark past demonstrations as in_past.

    Parameters
    ----------
    _tr : bool, optional
        If True, fetch all demonstrations regardless of date (default is False).

    Notes
    -----
    Prints statistics about the number of demonstrations processed, marked as
    past, and any errors encountered.
    """
    try:
        today = datetime.now().date()
        demos = fetch_upcoming_demos(_tr)
        stats = hide_past_demos(demos, today)
        print(f"Total demonstrations processed: {stats['total']}")
        print(f"Total demonstrations marked past: {stats['hidden']}")
        print(f"Total errors: {stats['errors']}")
    except Exception as e:
        print(f"Error hiding past demonstrations: {e}")


if __name__ == "__main__":
    with app.app_context():
        if os.getenv("also_past"):
            hide_past(True)
        else:
            hide_past()
        print("Past demonstrations processed successfully.")
