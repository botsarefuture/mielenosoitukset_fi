"""
Send demonstration reminder emails to subscribed users.

This script should be run daily (e.g., via cron).
It sends reminders 1 week before, the day before at 9:00, and the day of at 9:00 or at least 2 hours before the demonstration.

Changelog
---------
- v4.2.0: Original stable version.
- v4.3.0: Full refactor with strict Numpydoc compliance and cleanup.
- v4.3.1: Bugfix to prevent multiple duplicate reminders being sent.

"""
import os
import sched
import time
from datetime import datetime, timedelta, time as dt_time
from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.emailer.EmailSender import EmailSender
from mielenosoitukset_fi.utils.classes import Demonstration

REMINDER_STAGES = [
    ("week_before", timedelta(days=7)),
    ("day_before", timedelta(days=1)),
    ("day_of", timedelta(days=0)),
]

REMINDER_HOURS = {
    "day_before": dt_time(9, 0),
    "day_of": dt_time(9, 0),
}

scheduler = sched.scheduler(timefunc=time.time, delayfunc=time.sleep)
email_sender = EmailSender()

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
        The reminder stage (``week_before``, ``day_before``, ``day_of``).

    Returns
    -------
    bool
        True if reminder should be sent now, False otherwise.
    """
    if stage == "week_before":
        target = datetime.combine(demo_date, demo_time) - timedelta(days=7)
        return target.date() == now.date() and now.time() >= dt_time(7, 0)
    if stage == "day_before":
        target = datetime.combine(demo_date, demo_time) - timedelta(days=1)
        send_time = REMINDER_HOURS["day_before"]
        return target.date() == now.date() and now.time() >= send_time
    if stage == "day_of":
        event_dt = datetime.combine(demo_date, demo_time)
        send_time = REMINDER_HOURS["day_of"]
        if now.date() == demo_date:
            if now.time() >= send_time and (event_dt - now) > timedelta(hours=2):
                return True
            if (event_dt - now) <= timedelta(hours=2) and now < event_dt:
                return True
        return False
    return False

def parse_time_string(time_str):
    """
    Parse a time string in ``HH:MM`` or ``HH:MM:SS`` format.

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
        Event date in ``YYYY-MM-DD`` format.
    start_time : str
        Event start time in ``HH:MM`` or ``HH:MM:SS`` format.
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
    dt_fmt = "%Y%m%dT%H%M%S"
    dt = datetime.strptime(f"{start_date} {start_time[:5]}", "%Y-%m-%d %H:%M")
    dtend = dt + timedelta(hours=2)
    dtstart_str = dt.strftime(dt_fmt)
    dtend_str = dtend.strftime(dt_fmt)
    ical = (
        "BEGIN:VCALENDAR\n"
        "VERSION:2.0\n"
        "PRODID:-//Mielenosoitukset.fi//EN\n"
        "BEGIN:VEVENT\n"
        f"SUMMARY:{title}\n"
        f"DTSTART:{dtstart_str}\n"
        f"DTEND:{dtend_str}\n"
        f"LOCATION:{address}, {city}\n"
        f"DESCRIPTION:{description or ''}\n"
        "END:VEVENT\n"
        "END:VCALENDAR"
    )
    return ical

def send_email_later(send_time, template_name, subject, recipients, context, attachments):
    """
    Wait until send_time, send email, and clean up temp files.

    Parameters
    ----------
    send_time : datetime
        When to send the email.
    template_name : str
        Email template to use.
    subject : str
        Email subject.
    recipients : list of str
        List of recipient email addresses.
    context : dict
        Context for the email template.
    attachments : list of dict
        List of attachments with keys: ``filename``, ``path``, ``mime_type``.
    """
    now = datetime.now()
    delay_seconds = (send_time - now).total_seconds()
    if delay_seconds > 0:
        time.sleep(delay_seconds)

    fixed_attachments = []
    for att in attachments:
        if "content" not in att and "path" in att:
            with open(att["path"], "rb") as f:
                content = f.read()
            fixed_attachments.append({
                "filename": att["filename"],
                "content": content,
                "mime_type": att["mime_type"]
            })
        else:
            fixed_attachments.append({k: v for k, v in att.items() if k != "path"})

    email_sender.queue_email(
        template_name=template_name,
        subject=subject,
        recipients=recipients,
        context=context,
        attachments=fixed_attachments,
    )
    email_sender._die_when_no_jobs()

def schedule_reminder(reminder, demo_obj, demo_date, demo_time, stage, db):
    """
    Schedule sending of reminder email at the right time.

    Parameters
    ----------
    reminder : dict
        Reminder document from DB.
    demo_obj : Demonstration
        Demonstration object.
    demo_date : datetime.date
        Date of the demonstration.
    demo_time : datetime.time
        Start time of the demonstration.
    stage : str
        Reminder stage.
    db : Database
        Database instance for updating sent stages.
    """
    now = datetime.now()
    if stage == "week_before":
        send_datetime = datetime.combine(demo_date, demo_time) - timedelta(days=7)
        send_datetime = send_datetime.replace(hour=7, minute=0, second=0, microsecond=0)
    elif stage == "day_before":
        send_datetime = datetime.combine(demo_date, REMINDER_HOURS["day_before"]) - timedelta(days=1)
    elif stage == "day_of":
        event_dt = datetime.combine(demo_date, demo_time)
        send_datetime = datetime.combine(demo_date, REMINDER_HOURS["day_of"])
        if (event_dt - now) <= timedelta(hours=2):
            send_datetime = now
    else:
        send_datetime = now

    ical_text = generate_ical_event(
        title=demo_obj.title,
        start_date=demo_obj.date,
        start_time=demo_obj.start_time,
        city=demo_obj.city,
        address=demo_obj.address,
        description=getattr(demo_obj, 'description', None),
    )
    filename = f"{demo_obj.title}_{demo_obj.date}_{stage}.ics"
    filepath = f"/tmp/{filename}"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(ical_text)

    attachments = [
        {
            "filename": filename,
            "path": filepath,
            "mime_type": "text/calendar"
        }
    ]

    # Mark as sent immediately to avoid duplicates
    db["demo_reminders"].update_one(
        {"_id": reminder["_id"]},
        {"$push": {"sent_stages": stage}}
    )

    scheduler.enterabs(
        send_datetime.timestamp(),
        1,
        send_email_later,
        argument=(send_datetime, "demo_reminder.html", f"Muistutus: {demo_obj.title} {demo_obj.date}",
                  [reminder["user_email"]],
                  {
                      "title": demo_obj.title,
                      "date": demo_obj.date,
                      "start_time": demo_obj.start_time,
                      "city": demo_obj.city,
                      "address": demo_obj.address,
                      "stage": stage,
                      "ical_event": ical_text,
                      "demo_id": str(demo_obj._id),
                  },
                  attachments)
    )

def send_reminders_scheduled(override_email=None, force_all=False):
    """
    Fetch reminders from the database and schedule email sending.

    Parameters
    ----------
    override_email : str, optional
        If set, all reminders will be sent to this email address.
    force_all : bool, optional
        If True, force sending all reminders regardless of stage status.
    """
    db_manager = DatabaseManager().get_instance()
    db = db_manager.get_db()
    reminders = db["demo_reminders"]
    demos = db["demonstrations"]
    now = datetime.now()

    for reminder in reminders.find():
        demo = demos.find_one({"_id": reminder["demonstration_id"]})
        if not demo:
            continue
        if demo.get("cancelled"):
            continue
        demo_obj = Demonstration.from_dict(demo)
        demo_date = datetime.strptime(demo_obj.date, "%Y-%m-%d").date()
        demo_time = parse_time_string(demo_obj.start_time)
        demo_datetime = datetime.combine(demo_date, demo_time)

        if demo_datetime < now:
            continue

        sent_stages = reminder.get("sent_stages", [])

        for stage, _ in REMINDER_STAGES:
            if stage in sent_stages and not override_email:
                continue

            if force_all or should_send_reminder(demo_date, demo_time, now, stage):
                schedule_reminder(reminder, demo_obj, demo_date, demo_time, stage, db)

    scheduler.run()

def main():
    """Main entry point for scheduling reminders."""
    send_reminders_scheduled()

if __name__ == "__main__":
    main()
