"""
Send demonstration reminder emails to subscribed users.

This script should be run daily (e.g., via cron).
It sends reminders 1 week before, the day before at 9:00, and the day of at 9:00 or at least 2 hours before the demonstration.

Fields use underscore naming. Docstrings are in numpydoc format.
"""
from datetime import datetime, timedelta, time
from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.emailer.EmailSender import EmailSender
from mielenosoitukset_fi.utils.classes import Demonstration
from bson.objectid import ObjectId

REMINDER_STAGES = [
    ("week_before", timedelta(days=7)),
    ("day_before", timedelta(days=1)),
    ("day_of", timedelta(days=0)),
]

REMINDER_HOURS = {
    "day_before": time(9, 0),
    "day_of": time(9, 0),
}


def should_send_reminder(demo_date, demo_time, now, stage):
    """
    Determine if a reminder should be sent for a given stage.

    Parameters
    ----------
    demo_date : datetime.date
        The date of the demonstration.
    demo_time : datetime.time
        The start time of the demonstration.
    now : datetime
        The current datetime.
    stage : str
        The reminder stage (week_before, day_before, day_of).

    Returns
    -------
    bool
        True if reminder should be sent now, False otherwise.
    """
    if stage == "week_before":
        target = datetime.combine(demo_date, demo_time) - timedelta(days=7)
        return target.date() == now.date() and now.time() >= time(7, 0)
    elif stage == "day_before":
        target = datetime.combine(demo_date, demo_time) - timedelta(days=1)
        send_time = REMINDER_HOURS["day_before"]
        return target.date() == now.date() and now.time() >= send_time
    elif stage == "day_of":
        event_dt = datetime.combine(demo_date, demo_time)
        send_time = REMINDER_HOURS["day_of"]
        send_dt = datetime.combine(demo_date, send_time)
        # Send at 9:00 or at least 2 hours before event
        if now.date() == demo_date:
            if now.time() >= send_time and (event_dt - now) > timedelta(hours=2):
                return True
            elif (event_dt - now) <= timedelta(hours=2) and now < event_dt:
                return True
        return False
    return False

def main():
    """
    Main function to send demonstration reminders.
    """
    db_manager = DatabaseManager().get_instance()
    db = db_manager.get_db()
    reminders = db["demo_reminders"]
    demos = db["demonstrations"]
    email_sender = EmailSender()
    now = datetime.now()

    for reminder in reminders.find():
        demo = demos.find_one({"_id": reminder["demonstration_id"]})
        if not demo:
            continue
        demo_obj = Demonstration.from_dict(demo)
        demo_date = datetime.strptime(demo_obj.date, "%Y-%m-%d").date()
        demo_time = datetime.strptime(demo_obj.start_time, "%H:%M").time()
        sent_stages = reminder.get("sent_stages", [])
        for stage, _ in REMINDER_STAGES:
            if stage in sent_stages:
                continue
            if should_send_reminder(demo_date, demo_time, now, stage):
                # Send email
                email_sender.queue_email(
                    template_name="demo_reminder.html",
                    subject=f"Muistutus: {demo_obj.title} {demo_obj.date}",
                    recipients=[reminder["user_email"]],
                    context={
                        "title": demo_obj.title,
                        "date": demo_obj.date,
                        "start_time": demo_obj.start_time,
                        "city": demo_obj.city,
                        "address": demo_obj.address,
                        "stage": stage,
                    },
                )
                reminders.update_one(
                    {"_id": reminder["_id"]},
                    {"$push": {"sent_stages": stage}}
                )

if __name__ == "__main__":
    main()
