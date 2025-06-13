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


def send_reminders(override_email=None, force_all=False):
    """
    Send demonstration reminders to subscribers or to a specific email if override_email is given.

    Parameters
    ----------
    override_email : str or None
        If provided, send all reminders to this email address instead of the subscriber's email.
    force_all : bool
        If True, send all reminders regardless of timing.
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
        demo_time = parse_time_string(demo_obj.start_time)
        sent_stages = reminder.get("sent_stages", [])
        for stage, _ in REMINDER_STAGES:
            if stage in sent_stages and not override_email:
                continue
            if force_all or should_send_reminder(demo_date, demo_time, now, stage):
                ical_event = generate_ical_event(
                    title=demo_obj.title,
                    start_date=demo_obj.date,
                    start_time=demo_obj.start_time,
                    city=demo_obj.city,
                    address=demo_obj.address,
                    description=getattr(demo_obj, 'description', None),
                )
                
                # save ical event as an attachment
                ical_event = ical_event.encode("utf-8")
                with open(f"{demo_obj.title}_{demo_obj.date}.ics", "wb") as f:
                    f.write(ical_event)
                if isinstance(ical_event, str):
                    ical_content = ical_event.encode("utf-8")
                else:
                    ical_content = ical_event
                attachments = [
                    {
                        "filename": f"{demo_obj.title}_{demo_obj.date}.ics",
                        "content": ical_content,
                        "mime_type": "text/calendar"
                    }
                ]
                email_sender.queue_email(
                    template_name="demo_reminder.html",
                    subject=f"Muistutus: {demo_obj.title} {demo_obj.date}",
                    recipients=[override_email or reminder["user_email"]],
                    context={
                        "title": demo_obj.title,
                        "date": demo_obj.date,
                        "start_time": demo_obj.start_time,
                        "city": demo_obj.city,
                        "address": demo_obj.address,
                        "stage": stage,
                        "ical_event": ical_event,
                        "demo_id": str(demo_obj._id),
                    },
                    attachments=attachments
                )
                if not override_email and not force_all:
                    reminders.update_one(
                        {"_id": reminder["_id"]},
                        {"$push": {"sent_stages": stage}}
                    )
    email_sender._die_when_no_jobs()
    


def parse_time_string(time_str):
    """
    Parse a time string in 'HH:MM' or 'HH:MM:SS' format.

    Parameters
    ----------
    time_str : str
        The time string to parse.

    Returns
    -------
    datetime.time
        The parsed time object.

    Raises
    ------
    ValueError
        If the time string is not in a recognized format.
    """
    from datetime import datetime
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(time_str, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Invalid time format: {time_str}")


def generate_ical_event(title, start_date, start_time, city, address, description=None):
    """
    Generate an iCalendar (ICS) event string for a demonstration.

    Parameters
    ----------
    title : str
        Event title.
    start_date : str
        Event date in 'YYYY-MM-DD' format.
    start_time : str
        Event start time in 'HH:MM' or 'HH:MM:SS' format.
    city : str
        Event city.
    address : str
        Event address.
    description : str, optional
        Event description.

    Returns
    -------
    str
        iCalendar event as a string.
    """
    from datetime import datetime, timedelta
    dt_fmt = "%Y%m%dT%H%M%S"
    dt = datetime.strptime(f"{start_date} {start_time[:5]}", "%Y-%m-%d %H:%M")
    dtend = dt + timedelta(hours=2)  # Default: 2h event
    dtstart_str = dt.strftime(dt_fmt)
    dtend_str = dtend.strftime(dt_fmt)
    ical = f"""BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Mielenosoitukset.fi//EN\nBEGIN:VEVENT\nSUMMARY:{title}\nDTSTART:{dtstart_str}\nDTEND:{dtend_str}\nLOCATION:{address}, {city}\nDESCRIPTION:{description or ''}\nEND:VEVENT\nEND:VCALENDAR"""
    return ical


def main():
    """
    Main function to send demonstration reminders.
    """
    send_reminders()


if __name__ == "__main__":
    main()
