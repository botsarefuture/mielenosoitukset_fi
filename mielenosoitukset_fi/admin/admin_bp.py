from datetime import datetime, timezone, timedelta
import json
from mielenosoitukset_fi.utils.logger import logger

import os

from collections import defaultdict
import pytz

from bson.objectid import ObjectId
from flask import (
    Blueprint,
    abort,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
    stream_template,
    stream_with_context,
)
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from mielenosoitukset_fi.users.models import User  # Import User model
from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.wrappers import admin_required, permission_required

from mielenosoitukset_fi.utils.flashing import flash_message
from mielenosoitukset_fi.utils.analytics import get_demo_views

from mielenosoitukset_fi.utils.classes import AdminActivity
from .utils import AdminActParser, log_admin_action_V2, _ADMIN_TEMPLATE_FOLDER

# Constants
LOG_FILE_PATH = "app.log"

HELSINKI_TZ = pytz.timezone("Europe/Helsinki")


# Blueprint setup
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# Initialize MongoDB and Flask-Login
db_manager = DatabaseManager().get_instance()
mongo = db_manager.get_db()

login_manager = LoginManager()
login_manager.login_view = "users.auth.login"

from .utils import AdminActParser, log_admin_action_V2


@admin_bp.before_request
def log_request_info():
    try:
        """Log request information before handling it."""
        if current_user and current_user is not None:
            log_admin_action_V2(
                AdminActParser().log_request_info(request.__dict__, current_user)
            )
        else:
            log_admin_action_V2(AdminActParser().log_request_info(request.__dict__, {}))
    except Exception as e:
        logger.error(e)
        pass


class DemoViewCount:
    """ """

    def __init__(self, demo_id, count):
        self.id = demo_id
        self.views = count

    def __repr__(self):
        return f"DemoViewCount({self.id}, {self.views})"

    def __str__(self):
        return f"Demo ID: {self.id}, Count: {self.views}"


def count_per_demo(data):
    """

    Parameters
    ----------
    data :


    Returns
    -------


    """
    demo_count = {}
    for view in data:
        demo_id = view.get("demo_id")
        if demo_id in demo_count:
            demo_count[demo_id] += 1
        else:
            demo_count[demo_id] = 1

    demo_count = [
        DemoViewCount(demo_id, count) for demo_id, count in demo_count.items()
    ]
    return demo_count

def get_per_demo_anal(demo_id):
    analytics = mongo["d_analytics"].find_one({"_id": ObjectId(demo_id)})
    
    return analytics


# User loader function
@login_manager.user_loader
def load_user(user_id):
    """Load a user from the database using their ID.

    Parameters
    ----------
    user_id :


    Returns
    -------


    """
    user_doc = mongo.users.find_one({"_id": ObjectId(user_id)})
    return User.from_db(user_doc) if user_doc else None


# Admin dashboard
@admin_bp.route("/dashboard")
@login_required
@admin_required
def admin_dashboard():
    """Render the admin dashboard."""
    return render_template(f"{_ADMIN_TEMPLATE_FOLDER}dashboard.html")


def get_admin_activity(page=1, per_page=20):
    """Get the admin activity log with pagination.

    Parameters
    ----------
    page : int, optional
        The page number to retrieve, by default 1
    per_page : int, optional
        The number of items per page, by default 20

    Returns
    -------
    list
        A list of admin activity logs for the specified page
    """
    skip = (page - 1) * per_page
    activity = mongo.admin_logs.find({}).sort("_id", -1).skip(skip).limit(per_page)
    return [AdminActivity.from_dict(doc).to_dict(True) for doc in activity]


# Admin statistics page
@admin_bp.route("/stats")
@login_required
@admin_required
def stats():
    """Render statistics page with user and organization data.

    Returns
    -------
    str
        Rendered HTML template for the statistics page
    """
    try:
        total_users = mongo.users.count_documents({})
        active_users = mongo.users.count_documents({"confirmed": True})
        total_organizations = mongo.organizations.count_documents({})

        # Count users by role
        role_counts = get_user_role_counts()

        data = get_demo_views()
        data = count_per_demo(data)

        # Render statistics template
        return render_template(
            f"{_ADMIN_TEMPLATE_FOLDER}stats.html",
            total_users=total_users,
            total_organizations=total_organizations,
            role_counts=role_counts,
            active_users=active_users,
            data=data,
        )
    except Exception as e:
        logger.error(f"Error rendering stats page: {e}")
        flash_message("An error occurred while loading statistics.", "danger")
        return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/logs")
@login_required
@admin_required
@permission_required("VIEW_LOGS")
def logs():
    return render_template(f"{_ADMIN_TEMPLATE_FOLDER}logs.html")


@admin_bp.route("/api/logs")
@login_required
@admin_required
@permission_required("VIEW_LOGS")
def api_logs():
    """API endpoint to fetch admin logs with pagination.

    Parameters
    ----------
    page : int, optional
        The page number to retrieve, by default 1
    per_page : int, optional
        The number of items per page, by default 20

    Returns
    -------
    dict
        A dictionary containing the logs and pagination info
    """
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
        logs = get_admin_activity(page, per_page)
        total_logs = mongo.admin_logs.count_documents({})
        total_pages = (total_logs + per_page - 1) // per_page

    except Exception as e:
        logger.error(e)
        raise Exception from e

    return {
        "logs": logs,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "total_logs": total_logs,
    }, {"Content-Type": "application/json"}


def get_user_role_counts():
    """Fetch the count of users by role."""
    user_roles = mongo.users.aggregate(
        [{"$group": {"_id": "$role", "count": {"$sum": 1}}}]
    )
    return {role["_id"]: role["count"] for role in user_roles}

@admin_bp.route("/demo_analytics")
@login_required
@admin_required
@permission_required("VIEW_ANALYTICS")
def admin_analytics():
    """ """
    return demo_analytics()


def demo_analytics():
    """ """
    data = get_demo_views()
    data = count_per_demo(data)

    return render_template(f"{_ADMIN_TEMPLATE_FOLDER}analytics.html", data=data)


def send_red_alert_email(user):
    """Send a red alert email to the user.

    Parameters
    ----------
    user :


    Returns
    -------


    """
    # Use email_sender
    from mielenosoitukset_fi.emailer import EmailSender

    email_sender = EmailSender()
    email_sender.queue_email(
        template_name="red_alert_email.html",
        subject="Red Alert",
        recipients=[user.email],
        context={"username": user.username},
    )



def validate_mfa_token(token):
    """Validate the MFA token.

    Parameters
    ----------
    token :


    Returns
    -------


    """
    # Implement your MFA token validation logic here
    return True  # Placeholder for actual validation logic
from datetime import timedelta

@admin_bp.route("/per_demo_analytics/<demo_id>")
def demo_analytics(demo_id):
    try:
        demo_oid = ObjectId(demo_id)
    except Exception:
        abort(404, "Invalid demo ID")

    anal = get_per_demo_anal(demo_oid)
    if not anal:
        abort(404, "No analytics data found")

    analytics = anal.get("analytics", {})
    from mielenosoitukset_fi.utils.classes import Demonstration

    demo_data = mongo["demonstrations"].find_one({"_id": demo_oid})
    demo = Demonstration.from_dict(demo_data)
    
    now_utc = datetime.now(timezone.utc)
    today_str = now_utc.strftime("%Y-%m-%d")

    # --- Views per minute for today (existing) ---
    total_views = 0
    views_today = 0
    labels = []
    data = []

    day_data = analytics.get(today_str, {})

    for hour in range(24):
        hour_str = str(hour)
        hour_data = day_data.get(hour_str, {})
        for minute in range(60):
            minute_str = str(minute)
            count = hour_data.get(minute_str, 0)
            total_views += count
            views_today += count
            labels.append(f"{hour:02d}:{minute:02d}")
            data.append(count)

    avg_views_per_minute = (views_today / 1440) if views_today else 0

    # --- NEW: Views per day for last 30 days ---
    daily_labels = []
    daily_data = []
    for i in range(29, -1, -1):  # 30 days ago -> today
        day = now_utc - timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        day_views = 0
        day_hours = analytics.get(day_str, {})
        for hour_data in day_hours.values():
            day_views += sum(hour_data.values())
        daily_labels.append(day.strftime("%d.%m"))  # day.month format
        daily_data.append(day_views)

    # --- NEW: Views per week for last 52 weeks ---
    weekly_labels = []
    weekly_data = []

    # Create a helper to get Monday of the week for any date
    def get_monday(date):
        return date - timedelta(days=date.weekday())

    monday_today = get_monday(now_utc)

    for i in range(51, -1, -1):  # 52 weeks ago -> this week
        week_start = monday_today - timedelta(weeks=i)
        week_end = week_start + timedelta(days=6)

        week_label = f"{week_start.strftime('%d.%m')} - {week_end.strftime('%d.%m')}"
        weekly_labels.append(week_label)

        # sum views for each day in the week
        week_views = 0
        for d in range(7):
            day = week_start + timedelta(days=d)
            day_str = day.strftime("%Y-%m-%d")
            day_hours = analytics.get(day_str, {})
            for hour_data in day_hours.values():
                week_views += sum(hour_data.values())

        weekly_data.append(week_views)

    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}per_demo_analytics.html",
        analytics=anal,
        total_views=total_views,
        views_today=views_today,
        avg_views_per_minute=round(avg_views_per_minute, 2),
        chart_labels=labels,
        chart_data=data,
        daily_labels=daily_labels,
        daily_data=daily_data,
        weekly_labels=weekly_labels,
        weekly_data=weekly_data,
        demo=demo
    )


from flask import render_template
from datetime import datetime, timedelta, timezone

from flask import request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from bson.objectid import ObjectId
from flask import request, render_template, abort

@admin_bp.route("/analytics/overall_24h")
def analytics_overall_24h():
    now        = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    yesterday  = now - timedelta(days=1)

    # ── 1️⃣  Interval from query string ──────────────────────────
    try:
        interval = int(request.args.get("interval", 5))
        assert interval in {1, 5, 15, 30, 60, 120}
    except (ValueError, AssertionError):
        interval = 5                                             # safe default

    # ── 2️⃣  Build empty timeline – keys are **bucket start** UTC ─
    timeline   = defaultdict(int)                               # minute‑bucket → views
    label_map  = {}                                              # bucket → pretty label

    cur = yesterday
    while cur <= now:
        key              = cur.strftime("%Y-%m-%d %H:%M")        # canonical key
        timeline[key]    = 0
        label_map[key]   = (cur.strftime("%Y-%m-%d %H:%M")
                            if cur.date() != now.date()
                            else cur.strftime("%H:%M"))
        cur += timedelta(minutes=interval)

    # ── 3️⃣  Aggregate all demos into those buckets ──────────────
    for doc in mongo["d_analytics"].find({}, {"analytics": 1}):
        analytics = doc.get("analytics", {})

        # only two days are relevant for a moving 24 h window
        for day_str in {yesterday.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")}:
            for hour_str, hour_data in analytics.get(day_str, {}).items():
                for minute_str, count in hour_data.items():
                    # zero‑pad minutes to guarantee “%M” matches
                    minute = f"{int(minute_str):02d}"
                    try:
                        ts = datetime.strptime(
                            f"{day_str} {hour_str}:{minute}", "%Y-%m-%d %H:%M"
                        ).replace(tzinfo=timezone.utc)
                    except ValueError:
                        continue

                    if not (yesterday <= ts <= now):
                        continue

                    # Bucket start for this interval
                    rounded = ts - timedelta(
                        minutes=ts.minute % interval,
                        seconds=ts.second,
                        microseconds=ts.microsecond
                    )

                    key = rounded.strftime("%Y-%m-%d %H:%M")
                    timeline[key] += count

    # ── 4️⃣  Prepare data for Chart.js ───────────────────────────
    sorted_keys = sorted(timeline.keys())

    # Always (re)generate label_map here to avoid KeyErrors
    label_map = {
        k: (datetime.strptime(k, "%Y-%m-%d %H:%M").strftime("%Y-%m-%d %H:%M")
            if datetime.strptime(k, "%Y-%m-%d %H:%M").date() != now.date()
            else datetime.strptime(k, "%Y-%m-%d %H:%M").strftime("%H:%M"))
        for k in sorted_keys
    }

    labels = [label_map[k] for k in sorted_keys]
    data   = [timeline[k] for k in sorted_keys]


    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}overall_24h_analytics.html",
        chart_labels = labels,
        chart_data   = data,
        interval     = interval          # so the template can show current setting / dropdown
    )


@admin_bp.route("/api/analytics/overall_24h")
def analytics_overall_24h_api():
    now_hel = datetime.now(HELSINKI_TZ).replace(second=0, microsecond=0)
    yesterday_hel = now_hel - timedelta(days=1)

    try:
        interval = int(request.args.get("interval", 5))
        assert interval in {1,5,15,30,60,120}
    except Exception:
        interval = 5

    timeline = defaultdict(int)

    # Get all docs from d_analytics collection
    for doc in mongo["d_analytics"].find({}, {"analytics": 1}):
        analytics = doc.get("analytics", {})

        for day_str, hours in analytics.items():  # "2024-11-21"
            for hour_str, minutes in hours.items():  # "17"
                for minute_str, count in minutes.items():  # "53"
                    try:
                        dt_hel = datetime.strptime(
                            f"{day_str} {hour_str}:{minute_str}", "%Y-%m-%d %H:%M"
                        )
                        # attach Helsinki tz info
                        dt_hel = HELSINKI_TZ.localize(dt_hel)

                        # skip if outside last 24h window
                        if not (yesterday_hel <= dt_hel <= now_hel):
                            continue

                        # round down to interval
                        rounded = dt_hel - timedelta(
                            minutes=dt_hel.minute % interval,
                            seconds=dt_hel.second,
                            microseconds=dt_hel.microsecond
                        )
                        key = rounded.strftime("%Y-%m-%d %H:%M")
                        timeline[key] += count
                    except Exception:
                        continue

    # Prepare output arrays
    sorted_keys = sorted(timeline.keys())
    labels = []
    data = []

    for k in sorted_keys:
        dt = datetime.strptime(k, "%Y-%m-%d %H:%M").replace(tzinfo=HELSINKI_TZ)
        label = dt.strftime("%Y-%m-%d %H:%M") if dt.date() != now_hel.date() else dt.strftime("%H:%M")
        labels.append(label)
        data.append(timeline[k])

    return jsonify({
        "labels": labels,
        "data": data,
        "interval": interval
    })
