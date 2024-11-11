from datetime import datetime

import importlib, os, sys

# Get the parent directory
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_dir)

classes = importlib.import_module("classes")
database_manager = importlib.import_module("database_manager")
app = importlib.import_module("app").create_minimal()


DatabaseManager = database_manager.DatabaseManager
Demonstration = classes.Demonstration

# Get the database instance
db_manager = DatabaseManager().get_instance()
db = db_manager.get_db()


def is_future_demo(demo_date, today):
    """Check if the demonstration is in the future."""
    return demo_date >= today


def hide_past():
    """Mark past demonstrations as hidden.

    Changelog:
    ----------
    v2.4.0:
    - Added this function

    Roadmap:
    --------
    v2.6.0
    """
    try:
        # Get the current date
        today = datetime.now().date()

        # Fetch upcoming demonstrations that are not in the past
        demos = list(
            db["demonstrations"].find({"approved": True, "hide": {"$exists": False}})
        )

        # Iterate through the demonstrations and hide past ones
        for demo in demos:
            demo_date = datetime.strptime(demo["date"], "%d.%m.%Y").date()
            if not is_future_demo(demo_date, today):
                demonstration_instance = Demonstration.from_dict(demo)
                demonstration_instance.hide = True
                demonstration_instance.save()

    except Exception as e:
        print(f"Error hiding past demonstrations: {e}")


if __name__ == "__main__":
    with app.app_context():
        hide_past()
