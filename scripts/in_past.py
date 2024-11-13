"""
This script is responsible for hiding past demonstrations in the database.

Modules:
    datetime: Provides classes for manipulating dates and times.
    importlib: Provides the implementation of the import statement.
    os: Provides a way of using operating system dependent functionality.
    sys: Provides access to some variables used or maintained by the interpreter.

Functions:
    is_future_demo(demo_date, today):
        Checks if the given demonstration date is in the future compared to today's date.
    
    fetch_upcoming_demos():
        Fetches upcoming demonstrations from the database that are not in the past.
    
    hide_past_demos(demos, today):
        Iterates through the list of demonstrations and hides those that are in the past.
    
    hide_past():
        Main function that marks past demonstrations as hidden by fetching the upcoming demonstrations and processing them.

Usage:
    This script is intended to be run as a standalone module. When executed, it will mark past demonstrations as hidden in the database.
"""

import importlib
import os
import sys
from datetime import datetime

# Get the parent directory
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_dir)

# Import necessary modules
classes = importlib.import_module("classes")
database_manager = importlib.import_module("database_manager")
app = importlib.import_module("app").create_app()
utils = importlib.import_module("utils")

# Get the database instance
DatabaseManager = database_manager.DatabaseManager
Demonstration = classes.Demonstration
RecurringDemonstration = classes.RecurringDemonstration
db_manager = DatabaseManager().get_instance()
db = db_manager.get_db()

def is_future_demo(demo_date, today):
    """Check if the demonstration is in the future."""
    return demo_date >= today

def fetch_upcoming_demos():
    """Fetch upcoming demonstrations that are not in the past."""
    return list(db["demonstrations"].find(utils.variables.DEMO_FILTER))

def hide_past_demos(demos, today):
    """
    Hide past demonstrations by setting their 'hide' attribute to True and saving the changes.

    Args:
        demos (list): A list of dictionaries, each representing a demonstration with at least a 'date' key.
        today (datetime.date): The current date to compare demonstration dates against.

    Returns:
        None

    Raises:
        Prints an error message if there is an issue processing a demonstration.
    """
    
    for demo in demos:
        try:
            demo_date = datetime.strptime(demo["date"], "%d.%m.%Y").date()
            if not is_future_demo(demo_date, today):
                try:
                    demonstration_instance = Demonstration.from_dict(demo)
                except Exception as e:
                    demonstration_instance = RecurringDemonstration.from_dict(demo)
                demonstration_instance.hide = True
                demonstration_instance.save()
        except Exception as e:
            print(f"Error processing demonstration {demo['_id']}: {e}")

def hide_past():
    """Mark past demonstrations as hidden."""
    try:
        today = datetime.now().date()
        demos = fetch_upcoming_demos()
        hide_past_demos(demos, today)
    except Exception as e:
        print(f"Error hiding past demonstrations: {e}")

if __name__ == "__main__":
    with app.app_context():
        hide_past()
        print("Past demonstrations hidden successfully.")
