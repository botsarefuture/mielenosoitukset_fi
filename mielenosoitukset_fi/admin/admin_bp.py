import os
import json
import pytz
from collections import defaultdict
from datetime import datetime, timedelta, timezone

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
    jsonify
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
from mielenosoitukset_fi.utils.logger import logger
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
from math import ceil
from flask import request, render_template

@admin_bp.route("/stats")
@login_required
@admin_required
def stats():
    """Render statistics page with user, organization, and demo analytics."""
    try:
        total_users = mongo.users.count_documents({})
        active_users = mongo.users.count_documents({"confirmed": True})
        total_organizations = mongo.organizations.count_documents({})

        # Count users by role
        role_counts = get_user_role_counts()

        # Demo analytics data
        data = get_demo_views()
        data = count_per_demo(data)  # this returns a list of demo dicts

        # --- Pagination ---
        per_page = int(request.args.get("per_page", 20))
        page = int(request.args.get("page", 1))
        total_count = len(data)
        total_pages = ceil(total_count / per_page)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        data_page = data[start_idx:end_idx]

        # Render template
        return render_template(
            f"{_ADMIN_TEMPLATE_FOLDER}stats.html",
            total_users=total_users,
            total_organizations=total_organizations,
            role_counts=role_counts,
            active_users=active_users,
            data=data_page,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            total_count=total_count
        )
    except Exception as e:
        logger.error(f"Error rendering stats page: {e}")
        flash_message("An error occurred while loading statistics.", "danger")
        return redirect(url_for("admin.admin_dashboard"))

@admin_bp.route("/manual/")
def manual():
    return render_template("manuals/index.html")

@admin_bp.route("/manual/<path:page>")
def manual_page(page):
    return render_template(f"manuals/{page}.html")

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
    from mielenosoitukset_fi.utils.classes import Demonstration
    try:
        demo_oid = ObjectId(demo_id)
    except Exception:
        abort(404, "Invalid demo ID")

    anal = get_per_demo_anal(demo_oid)
    if not anal:
        abort(404, "No analytics data found")

    analytics = anal.get("analytics", {})
    demo_data = mongo["demonstrations"].find_one({"_id": demo_oid})
    demo = Demonstration.from_dict(demo_data)

    now_utc = datetime.now(timezone.utc)
    today_str = now_utc.strftime("%Y-%m-%d")

    # --- Initialize variables ---
    total_views = 0
    views_today = 0
    labels = []
    data = []

    # --- Per minute today ---
    day_data = analytics.get(today_str, {})
    for hour in range(24):
        hour_str = str(hour)
        hour_data = day_data.get(hour_str, {})
        for minute in range(60):
            minute_str = str(minute)
            count = hour_data.get(minute_str, 0)
            total_views += count  # will sum all-time later
            views_today += count
            labels.append(f"{hour:02d}:{minute:02d}")
            data.append(count)

    # --- Add total views from all previous days ---
    for day_str, day_hours in analytics.items():
        if day_str != today_str:
            for hour_data in day_hours.values():
                total_views += sum(hour_data.values())

    avg_views_per_minute = (views_today / 1440) if views_today else 0

    # --- Views per day last 30 days ---
    daily_labels = []
    daily_data = []
    for i in range(29, -1, -1):  # 30 days ago -> today
        day = now_utc - timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        day_views = 0
        day_hours = analytics.get(day_str, {})
        for hour_data in day_hours.values():
            day_views += sum(hour_data.values())
        daily_labels.append(day.strftime("%d.%m"))
        daily_data.append(day_views)

    # --- Views per week last 52 weeks ---
    weekly_labels = []
    weekly_data = []

    def get_monday(date):
        return date - timedelta(days=date.weekday())

    monday_today = get_monday(now_utc)

    for i in range(51, -1, -1):  # 52 weeks ago -> this week
        week_start = monday_today - timedelta(weeks=i)
        week_end = week_start + timedelta(days=6)
        week_label = f"{week_start.strftime('%d.%m')} - {week_end.strftime('%d.%m')}"
        weekly_labels.append(week_label)

        week_views = 0
        for d in range(7):
            day = week_start + timedelta(days=d)
            day_str = day.strftime("%Y-%m-%d")
            day_hours = analytics.get(day_str, {})
            for hour_data in day_hours.values():
                week_views += sum(hour_data.values())
        weekly_data.append(week_views)

    # --- Render template ---
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


from datetime import datetime, timedelta, timezone
from collections import defaultdict
from bson.objectid import ObjectId
import math

def recommend_demos_no_user(top_n=5, weights=None):
    if weights is None:
        weights = {"trending": 0.5, "popularity": 0.3, "recency": 0.1, "category": 0.1}

    now_utc = datetime.now(timezone.utc)
    yesterday_utc = now_utc - timedelta(days=1)

    demo_scores = {}
    category_trending = defaultdict(int)

    # --- Step 1: Aggregate analytics and build category trending ---
    for doc in mongo["d_analytics"].find({}, {"analytics": 1}):
        demo_id = str(doc["_id"])
        analytics = doc.get("analytics", {})

        trending_views = 0
        total_views = 0

        for day_str, hours in analytics.items():
            for hour_str, minutes in hours.items():
                for minute_str, count in minutes.items():
                    try:
                        dt = datetime.strptime(f"{day_str} {hour_str}:{minute_str}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                        total_views += count
                        if yesterday_utc <= dt <= now_utc:
                            trending_views += count
                    except Exception:
                        continue

        demo_scores[demo_id] = {"trending": trending_views, "popularity": total_views}

        # Fetch demo tags
        demo = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)}, {"tags": 1, "created_at": 1})
        tags = demo.get("tags", []) if demo else []
        demo_scores[demo_id]["tags"] = tags
        demo_scores[demo_id]["created_at"] = demo.get("created_at", now_utc - timedelta(days=30)) if demo else now_utc - timedelta(days=30)

        for tag in tags:
            category_trending[tag] += trending_views

    # Normalize trending and popularity
    max_trending = max([v["trending"] for v in demo_scores.values()] + [1])
    max_popularity = max([v["popularity"] for v in demo_scores.values()] + [1])
    max_category = max(category_trending.values() or [1])

    for demo_id, scores in demo_scores.items():
        scores["trending"] /= max_trending
        scores["popularity"] /= max_popularity
        scores["recency"] = math.exp(-(now_utc - scores["created_at"]).days / 30)
        scores["category"] = sum(category_trending[tag] for tag in scores["tags"]) / max_category

        scores["final_score"] = sum(scores[k] * weights[k] for k in weights)

    # Sort demos by final score
    top_demos = sorted(demo_scores.items(), key=lambda x: x[1]["final_score"], reverse=True)[:top_n]

    # Return enriched results
    results = []
    for d_id, scores in top_demos:
        demo = mongo.demonstrations.find_one({"_id": ObjectId(d_id)}, {"title": 1})
        results.append({
            "demo_id": d_id,
            "title": demo.get("title", "Unknown") if demo else "Unknown",
            "score": scores["final_score"]
        })

    return results

# route that returns the result of the recommend demos thin

@admin_bp.route("/api/demos/recommendations")
@login_required
def api_demos_recommendations():
    """
    Get demo recommendations for a user.
    """
    recommendations = recommend_demos_no_user()
    return jsonify(recommendations)

from flask import jsonify
from datetime import datetime, timedelta, timezone
@admin_bp.route("/api/demos/nousussa")
@login_required
@admin_required
@permission_required("VIEW_ANALYTICS")
def api_demos_nousussa():
    """
    List demos that are 'nousussa' (rising) — sorted by views in the last 24 hours.
    Accepts optional query parameter:
      - limit: number of demos to return (default 5)
    """
    now_utc = datetime.now(timezone.utc)
    yesterday_utc = now_utc - timedelta(days=1)

    # Get limit from query string, default to 5
    try:
        limit = int(request.args.get("limit", 5))
        limit = max(1, min(limit, 50))  # optional: cap at 50 to prevent abuse
    except ValueError:
        limit = 5

    demo_views = []

    # Fetch all demos analytics
    for doc in mongo["d_analytics"].find({}, {"analytics": 1, "_id": 1}):
        demo_id = str(doc["_id"])
        analytics = doc.get("analytics", {})

        views_last_24h = 0

        for day_str, hours in analytics.items():
            for hour_str, minutes in hours.items():
                for minute_str, count in minutes.items():
                    try:
                        dt = datetime.strptime(f"{day_str} {hour_str}:{minute_str}", "%Y-%m-%d %H:%M")
                        dt = dt.replace(tzinfo=timezone.utc)
                        if yesterday_utc <= dt <= now_utc:
                            views_last_24h += count
                    except Exception:
                        continue

        if views_last_24h > 0:
            demo_views.append({
                "demo_id": demo_id,
                "views_last_24h": views_last_24h
            })

    # Sort demos descending by views_last_24h
    demo_views.sort(key=lambda x: x["views_last_24h"], reverse=True)

    # Limit results
    demo_views = demo_views[:limit]

    # Optionally, fetch demo names/titles
    for d in demo_views:
        demo_data = mongo["demonstrations"].find_one({"_id": ObjectId(d["demo_id"])}, {"title": 1})
        d["title"] = demo_data.get("title") if demo_data else "Unknown"

    return jsonify({
        "demos": demo_views,
        "generated_at": now_utc.isoformat(),
        "limit": limit
    })


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
