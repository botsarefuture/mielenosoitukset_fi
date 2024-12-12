from flask import Flask, render_template
from mielenosoitukset_fi.database_manager import DatabaseManager
from datetime import datetime
from mielenosoitukset_fi.emailer.EmailSender import EmailSender
import logging

# Initialize the Flask app
app = Flask(__name__)

# Get the database instance
db_manager = DatabaseManager().get_instance()
db = db_manager.get_db()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def is_future_demo(demo: dict, today: datetime.date) -> bool:
    """
    Check if the demonstration is in the future.

    Parameters
    ----------
    demo : dict
        The demonstration record.
    today : datetime.date
        The current date.

    Returns
    -------
    bool
        True if the demonstration is in the future, False otherwise.
    """
    demo_date = datetime.strptime(demo["date"], "%d.%m.%Y").date()
    return demo_date >= today


def get_upcoming_demonstrations() -> list:
    """
    Fetch upcoming demonstrations.

    Returns
    -------
    list
        A list of upcoming demonstrations.
    """
    try:
        current_date = datetime.now().date()
        approved_demos = list(db["demonstrations"].find({"approved": True}))
        future_demos = [
            demo for demo in approved_demos if is_future_demo(demo, current_date)
        ]
        return future_demos
    except Exception as e:
        logger.error(f"Error fetching upcoming demonstrations: {e}")
        return []


def send_newsletter_to_users() -> None:
    """
    Render newsletters for each user and queue them for sending.

    Returns
    -------
    None
    """
    email_sender = EmailSender()

    try:
        admin_users = list(db["users"].find({"role": "global_admin"}))
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        admin_users = []

    upcoming_demonstrations = get_upcoming_demonstrations()

    for user in admin_users:
        context = {"user": user, "demonstrations": upcoming_demonstrations}
        email_sender.queue_email(
            template_name="newsletter.html",
            subject="Upcoming Demonstrations",
            recipients=[user.get("email")],
            context=context,
        )
        logger.info(f"Newsletter queued for user: {user.get('email')}")


with app.app_context():
    send_newsletter_to_users()
