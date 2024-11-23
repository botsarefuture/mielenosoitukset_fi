from flask import Flask, render_template
from database_manager import DatabaseManager
from datetime import datetime
from emailer.EmailSender import EmailSender

# Initialize the Flask app
app = Flask(__name__)

# Get the database instance
db_manager = DatabaseManager().get_instance()
db = db_manager.get_db()


def is_future_demo(demo, today):
    """Check if the demonstration is in the future."""
    demo_date = datetime.strptime(demo["date"], "%d.%m.%Y").date()
    return demo_date >= today


def get_upcoming_demonstrations():
    """Fetch upcoming demonstrations."""
    try:
        current_time = datetime.now().date()
        upcoming_demos = list(db["demonstrations"].find({"approved": True}))
        future_demos = [
            demo for demo in upcoming_demos if is_future_demo(demo, current_time)
        ]
        return future_demos
    except Exception as e:
        print(f"Error fetching upcoming demonstrations: {e}")
        return []


def send_newsletter_to_users():
    """Render newsletters for each user and queue them for sending."""
    email_sender = EmailSender()

    try:
        users = list(db["users"].find({"role": "global_admin"}))
    except Exception as e:
        print(f"Error fetching users: {e}")
        users = []

    upcoming_demonstrations = get_upcoming_demonstrations()

    for user in users:
        context = {"user": user, "demonstrations": upcoming_demonstrations}
        email_sender.queue_email(
            template_name="newsletter.html",
            subject="Upcoming Demonstrations",
            recipients=[user.get("email")],
            context=context,
        )
        print(f"Newsletter queued for user: {user.get('email')}")


with app.app_context():
    send_newsletter_to_users()
