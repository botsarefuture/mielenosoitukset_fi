import os
import json
import pytz
from collections import defaultdict
from typing import Any, Dict
from datetime import datetime, timedelta, timezone

from bson.objectid import ObjectId
from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
    stream_template,
    stream_with_context,
    jsonify,
    has_request_context,
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
from mielenosoitukset_fi.utils.cache import cache

from .utils import AdminActParser, log_admin_action_V2, _ADMIN_TEMPLATE_FOLDER

# Timezone for rolling analytics into Helsinki-local buckets
HELSINKI_TZ = pytz.timezone("Europe/Helsinki")
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


def _get_job_manager_or_abort():
    job_manager = current_app.extensions.get("job_manager")
    if not job_manager:
        abort(503, "Background jobs are not available in this deployment.")
    return job_manager


def _json_safe(value):
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return type(value)(_json_safe(v) for v in value)
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _log_admin_event(event: str, **details):
    """Structured logging helper for admin blueprint actions."""
    payload = {
        "event": event,
        "module": "admin_bp",
    }
    if has_request_context():
        payload.update(
            {
                "path": request.path,
                "method": request.method,
                "endpoint": request.endpoint,
            }
        )

    try:
        actor_id = None
        actor_username = None
        actor_email = None
        if current_user and not getattr(current_user, "is_anonymous", True):
            actor_id = (
                getattr(current_user, "id", None)
                or getattr(current_user, "_id", None)
                or (current_user.get_id() if hasattr(current_user, "get_id") else None)
            )
            actor_username = getattr(current_user, "username", None)
            actor_email = getattr(current_user, "email", None)
        payload["actor"] = {
            "id": str(actor_id) if actor_id else None,
            "username": actor_username,
            "email": actor_email,
        }
    except Exception:
        payload["actor"] = {"id": None, "username": None}

    if details:
        payload["details"] = _json_safe(details)

    try:
        log_admin_action_V2(payload)
    except Exception:
        logger.exception("Failed to log admin event: %s", event)


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


def _rollup_demo_analytics_on_demand(demo_id: ObjectId):
    """Build d_analytics doc for a demo from raw analytics if missing."""
    events = list(
        mongo["analytics"].find({"demo_id": demo_id}, {"timestamp": 1})
    )
    if not events:
        return None

    rolled = {}
    max_event_id = None
    for ev in events:
        ev_id = ev.get("_id")
        if ev_id is not None:
            max_event_id = ev_id if max_event_id is None else max(max_event_id, ev_id)
        ts = ev.get("timestamp")
        if not ts:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        ts_hel = ts.astimezone(HELSINKI_TZ)
        day_key = ts_hel.strftime("%Y-%m-%d")
        hour_key = f"{ts_hel.hour:02d}"
        minute_key = f"{ts_hel.minute:02d}"
        day_bucket = rolled.setdefault(day_key, {})
        hour_bucket = day_bucket.setdefault(hour_key, {})
        hour_bucket[minute_key] = hour_bucket.get(minute_key, 0) + 1

    doc = {"_id": demo_id, "analytics": rolled}
    mongo["d_analytics"].replace_one({"_id": demo_id}, doc, upsert=True)
    if max_event_id is not None:
        mongo["_meta"].update_one(
            {"_id": "analytics_rollup"},
            {"$max": {f"on_demand_max_ids.{str(demo_id)}": max_event_id}},
            upsert=True,
        )
    return doc

def get_per_demo_anal(demo_id):
    analytics = mongo["d_analytics"].find_one({"_id": ObjectId(demo_id)})
    if analytics:
        return analytics
    return _rollup_demo_analytics_on_demand(ObjectId(demo_id))


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

# Route to view dashboard
@admin_bp.route("/dashboard")
@login_required
@admin_required
def admin_dashboard():
    """Render the admin dashboard."""
    # Load current panic mode
    panic = mongo.panic.find_one({"name": "global"})
    panic_mode = panic.get("panic", False) if panic else False
    _log_admin_event("dashboard_view", panic_mode=panic_mode)
    return render_template(f"{_ADMIN_TEMPLATE_FOLDER}dashboard.html", panic_mode=panic_mode)


# Route to activate panic mode
@admin_bp.route("/dashboard/panic/activate", methods=["POST"])
@login_required
@admin_required
def activate_panic():
    """Activate global panic mode."""
    mongo.panic.update_one(
        {"name": "global"},
        {"$set": {"panic": True}},
        upsert=True
    )
    _log_admin_event("panic_mode_update", panic_mode=True)
    flash_message("Panic mode activated!", "success")
    return redirect(url_for("admin.admin_dashboard"))


# Route to deactivate panic mode
@admin_bp.route("/dashboard/panic/deactivate", methods=["POST"])
@login_required
@admin_required
def deactivate_panic():
    """Deactivate global panic mode."""
    mongo.panic.update_one(
        {"name": "global"},
        {"$set": {"panic": False}},
        upsert=True
    )
    _log_admin_event("panic_mode_update", panic_mode=False)
    flash_message("Panic mode deactivated!", "success")
    return redirect(url_for("admin.admin_dashboard"))


# Optional: route to get current status as JSON (useful for AJAX)
@admin_bp.route("/dashboard/panic/status", methods=["GET"])
@login_required
@admin_required
def panic_status():
    """Return current panic mode status as JSON."""
    panic = mongo.panic.find_one({"name": "global"})
    panic_mode = panic.get("panic", False) if panic else False
    _log_admin_event("panic_status_requested", panic_mode=panic_mode)
    return jsonify({"panic_mode": panic_mode})


@admin_bp.route("/dashboard/cache/clear", methods=["POST"])
@login_required
@admin_required
def clear_cache():
    """Allow admins to purge the application cache from the dashboard."""
    try:
        cache.clear()
        _log_admin_event("cache_cleared", status="success")
        flash_message("Välimuisti tyhjennettiin.", "success")
    except Exception as exc:
        logger.exception("Failed to clear cache via admin dashboard")
        _log_admin_event("cache_cleared", status="error", reason=str(exc))
        flash_message("Välimuistin tyhjennys epäonnistui.", "danger")
    return redirect(url_for("admin.admin_dashboard"))


def _serialize_login_log(doc: dict) -> dict:
    """Normalize a login log document for JSON responses."""
    timestamp = doc.get("timestamp")
    if isinstance(timestamp, datetime):
        timestamp_str = timestamp.replace(tzinfo=timezone.utc).isoformat()
        time_ago = datetime.utcnow() - timestamp
        minutes_ago = max(int(time_ago.total_seconds() // 60), 0)
    else:
        timestamp_str = ""
        minutes_ago = None

    return {
        "id": str(doc.get("_id")),
        "username": doc.get("username") or "unknown",
        "ip": doc.get("ip") or "—",
        "user_agent": doc.get("user_agent") or "",
        "reason": doc.get("reason") or "",
        "success": bool(doc.get("success")),
        "status": "success" if doc.get("success") else "failure",
        "user_id": str(doc.get("user_id")) if doc.get("user_id") else None,
        "timestamp": timestamp_str,
        "minutes_ago": minutes_ago,
    }


def _calculate_dashboard_snapshot() -> dict:
    """Aggregate lightweight metrics for the dashboard."""
    now = datetime.utcnow()
    last_hour = now - timedelta(hours=1)
    last_day = now - timedelta(days=1)

    login_coll = mongo.login_logs
    demos_coll = mongo.demonstrations

    total_users = mongo.users.count_documents({})
    confirmed_users = mongo.users.count_documents({"confirmed": True})
    pending_users = mongo.users.count_documents({"confirmed": False})
    admin_users = mongo.users.count_documents({"role": {"$in": ["admin", "global_admin", "moderator"]}})

    active_orgs = mongo.organizations.count_documents({"archived": {"$ne": True}})
    cases_open = mongo.cases.count_documents({"$or": [{"meta.closed": {"$ne": True}}, {"meta": {"$exists": False}}]})

    upcoming_demos = demos_coll.count_documents({"cancelled": {"$ne": True}, "hide": {"$ne": True}})
    pending_demos = demos_coll.count_documents({"approved": {"$ne": True}, "hide": {"$ne": True}})

    logins_last_hour = login_coll.count_documents({"timestamp": {"$gte": last_hour}})
    failed_logins_last_hour = login_coll.count_documents({"timestamp": {"$gte": last_hour}, "success": False})
    logins_last_day = login_coll.count_documents({"timestamp": {"$gte": last_day}})

    panic = mongo.panic.find_one({"name": "global"}) or {}

    success_rate = 0
    if logins_last_hour:
        success_rate = round(((logins_last_hour - failed_logins_last_hour) / logins_last_hour) * 100)

    return {
        "users": {
            "total": total_users,
            "confirmed": confirmed_users,
            "pending": pending_users,
            "admins": admin_users,
        },
        "organizations": {"active": active_orgs},
        "demos": {"live": upcoming_demos, "pending": pending_demos},
        "cases": {"open": cases_open},
        "logins": {
            "last_hour": logins_last_hour,
            "failed_last_hour": failed_logins_last_hour,
            "last_day": logins_last_day,
            "success_rate": success_rate,
        },
        "panic_mode": panic.get("panic", False),
        "generated_at": now.replace(tzinfo=timezone.utc).isoformat(),
    }


@admin_bp.route("/dashboard/data")
@login_required
@admin_required
def dashboard_data():
    """Return aggregated dashboard metrics for polling."""
    snapshot = _calculate_dashboard_snapshot()
    _log_admin_event("dashboard_snapshot_requested")
    return jsonify(snapshot)


@admin_bp.route("/dashboard/login-feed")
@login_required
@admin_required
def dashboard_login_feed():
    """Return the most recent login attempts for the realtime feed."""
    try:
        limit = int(request.args.get("limit", 20))
    except ValueError:
        limit = 20

    limit = max(5, min(limit, 100))

    logs_cursor = mongo.login_logs.find({}).sort("_id", -1).limit(limit)
    logs = [_serialize_login_log(doc) for doc in logs_cursor]
    _log_admin_event("login_feed_requested", limit=limit, returned=len(logs))
    return jsonify({"logs": logs})


@admin_bp.route("/background-jobs")
@login_required
@admin_required
@permission_required("VIEW_BACKGROUND_JOBS")
def background_jobs():
    """Dashboard for observing and controlling background jobs."""
    job_manager = _get_job_manager_or_abort()
    jobs = sorted(job_manager.list_jobs(), key=lambda job: job["name"].lower())
    selected_job = request.args.get("job")
    job_keys = {job["key"] for job in jobs}
    if selected_job not in job_keys:
        selected_job = None

    try:
        limit = min(int(request.args.get("limit", 50)), 200)
    except (TypeError, ValueError):
        limit = 50

    runs = job_manager.get_recent_runs(selected_job, limit=limit)

    _log_admin_event(
        "background_jobs_view",
        selected_job=selected_job,
        limit=limit,
        total_jobs=len(jobs),
    )
    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}background_jobs.html",
        jobs=jobs,
        runs=runs,
        selected_job=selected_job,
        limit=limit,
        scheduler_disabled=current_app.config.get("DISABLE_BACKGROUND_JOBS", False),
        can_manage=current_user.has_permission("MANAGE_BACKGROUND_JOBS"),
    )


@admin_bp.route("/background-jobs/<job_key>")
@login_required
@admin_required
@permission_required("VIEW_BACKGROUND_JOBS")
def background_job_detail(job_key):
    job_manager = _get_job_manager_or_abort()
    try:
        job = job_manager.get_job_info(job_key)
    except KeyError:
        abort(404)

    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    try:
        limit = min(200, max(10, int(request.args.get("limit", 25))))
    except (TypeError, ValueError):
        limit = 25

    skip = (page - 1) * limit
    runs = job_manager.get_recent_runs(job_key, limit=limit, skip=skip)
    total_runs = job_manager.count_runs(job_key)
    has_next = skip + limit < total_runs

    selected_run_id = request.args.get("run_id")
    changes_query: Dict[str, Any] = {"details.job_key": job_key}
    if selected_run_id:
        changes_query["details.job_run_id"] = selected_run_id

    change_logs = list(
        mongo.demo_audit_logs.find(changes_query)
        .sort("timestamp", -1)
        .limit(100)
    )

    _log_admin_event(
        "background_job_detail_view",
        job_key=job_key,
        page=page,
        limit=limit,
        selected_run_id=selected_run_id,
    )
    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}background_job_detail.html",
        job=job,
        runs=runs,
        page=page,
        limit=limit,
        total_runs=total_runs,
        has_next=has_next,
        can_manage=current_user.has_permission("MANAGE_BACKGROUND_JOBS"),
        change_logs=change_logs,
        selected_run_id=selected_run_id,
    )


@admin_bp.route("/background-jobs/<job_key>/run", methods=["POST"])
@login_required
@admin_required
@permission_required("MANAGE_BACKGROUND_JOBS")
def run_background_job(job_key):
    """Trigger a background job to run immediately."""
    job_manager = _get_job_manager_or_abort()
    job = job_manager.get_job(job_key)

    if not job.get("allow_manual_trigger", True):
        flash_message("This job cannot be run manually.", "danger")
        _log_admin_event("background_job_run_now", job_key=job_key, status="forbidden")
        return redirect(url_for("admin.background_jobs", job=job_key))

    triggered_by = f"admin:{current_user.get_id()}"
    metadata = {
        "user_id": str(getattr(current_user, "id", current_user.get_id())),
        "username": getattr(current_user, "username", None),
        "email": getattr(current_user, "email", None),
    }
    job_manager.run_job_now(job_key, triggered_by=triggered_by, metadata=metadata)
    _log_admin_event(
        "background_job_run_now",
        job_key=job_key,
        triggered_by=triggered_by,
        status="queued",
    )
    flash_message("Job queued to run now.", "success")
    return redirect(url_for("admin.background_jobs", job=job_key))


@admin_bp.route("/background-jobs/<job_key>/toggle", methods=["POST"])
@login_required
@admin_required
@permission_required("MANAGE_BACKGROUND_JOBS")
def toggle_background_job(job_key):
    """Enable or disable a background job."""
    job_manager = _get_job_manager_or_abort()
    enabled = request.form.get("enabled") == "1"
    job_manager.set_job_enabled(job_key, enabled)
    _log_admin_event("background_job_toggle", job_key=job_key, enabled=enabled)
    flash_message(
        f"Job {'enabled' if enabled else 'disabled'} successfully.",
        "success",
    )
    return redirect(url_for("admin.background_jobs", job=job_key))


@admin_bp.route("/background-jobs/<job_key>/schedule", methods=["POST"])
@login_required
@admin_required
@permission_required("MANAGE_BACKGROUND_JOBS")
def update_background_job_schedule(job_key):
    """Update the interval schedule for a job."""
    job_manager = _get_job_manager_or_abort()
    interval_value = request.form.get("interval_value")
    interval_unit = request.form.get("interval_unit")

    try:
        job_manager.update_interval(job_key, int(interval_value), interval_unit)
        _log_admin_event(
            "background_job_schedule_update",
            job_key=job_key,
            interval_value=interval_value,
            interval_unit=interval_unit,
            status="success",
        )
        flash_message("Schedule updated.", "success")
    except Exception as exc:  # pragma: no cover - defensive
        _log_admin_event(
            "background_job_schedule_update",
            job_key=job_key,
            interval_value=interval_value,
            interval_unit=interval_unit,
            status="error",
            reason=str(exc),
        )
        flash_message(f"Failed to update schedule: {exc}", "danger")

    return redirect(url_for("admin.background_jobs", job=job_key))


def _build_logs_query(filters: Dict[str, Any]) -> Dict[str, Any]:
    """Construct a MongoDB query for admin logs based on filter parameters."""
    clauses = []

    user_filter = filters.get("user")
    if user_filter:
        try:
            clauses.append({"user._id": ObjectId(user_filter)})
        except Exception:
            pass

    timestamp_range = {}
    start_date = filters.get("start_date")
    if start_date:
        try:
            timestamp_range["$gte"] = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            pass
    end_date = filters.get("end_date")
    if end_date:
        try:
            timestamp_range["$lt"] = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        except ValueError:
            pass
    if timestamp_range:
        clauses.append({"timestamp": timestamp_range})

    action_type = filters.get("action_type")
    if action_type:
        clauses.append({
            "$or": [
                {"request.method": action_type},
                {"action.method": action_type},
            ]
        })

    if not clauses:
        return {}
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _format_log_entry(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a raw admin log entry into a UI friendly payload."""
    request_data = doc.get("request") or doc.get("action") or {}
    legacy_action = None
    if not isinstance(request_data, dict):
        legacy_action = str(request_data)
        request_data = {}
    environ = request_data.get("environ") or {}
    headers = request_data.get("headers")

    def _extract_user_agent():
        ua = request_data.get("user_agent") or environ.get("HTTP_USER_AGENT")
        if ua:
            return ua
        if isinstance(headers, dict):
            return headers.get("User-Agent") or headers.get("user-agent")
        if isinstance(headers, str) and "User-Agent" in headers:
            try:
                return headers.split("User-Agent:")[1].split("\\r")[0].strip()
            except Exception:
                return headers
        return "—"

    method = request_data.get("method") or environ.get("REQUEST_METHOD") or "—"
    path = (
        request_data.get("path")
        or request_data.get("full_path")
        or request_data.get("url")
        or environ.get("PATH_INFO")
        or "—"
    )
    if legacy_action and method == "—":
        method = "ACTION"
    if legacy_action and path == "—":
        path = legacy_action
    remote_addr = request_data.get("remote_addr") or environ.get("REMOTE_ADDR") or "—"

    timestamp = doc.get("timestamp")
    if isinstance(timestamp, datetime):
        timestamp_display = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        timestamp_iso = timestamp.replace(tzinfo=timezone.utc).isoformat()
        rel_minutes = max(int((datetime.utcnow() - timestamp).total_seconds() // 60), 0)
    else:
        timestamp_display = str(timestamp) if timestamp else "—"
        timestamp_iso = timestamp_display
        rel_minutes = None

    user_doc = doc.get("user") or {}
    by = {
        "id": str(user_doc.get("_id")) if user_doc.get("_id") else None,
        "username": user_doc.get("username") or "Unknown",
        "displayname": user_doc.get("displayname") or user_doc.get("username") or "Unknown",
        "profile_picture": user_doc.get("profile_picture"),
        "email": user_doc.get("email"),
    }

    session_info = doc.get("session") or {}
    session_id = (
        session_info.get("sid")
        or session_info.get("session_id")
        or doc.get("session_id")
        or "—"
    )

    def _stringify_payload(value):
        if value in (None, "", {}, []):
            return ""
        if isinstance(value, (dict, list)):
            try:
                return json.dumps(value, ensure_ascii=False, default=str)
            except Exception:
                return str(value)
        return str(value)

    request_meta = {
        "endpoint": request_data.get("endpoint") or request_data.get("url_rule"),
        "blueprint": request_data.get("blueprint"),
        "full_path": request_data.get("full_path") or request_data.get("url"),
        "referrer": request_data.get("referrer")
        or (headers.get("Referer") if isinstance(headers, dict) else None),
        "view_args": _stringify_payload(request_data.get("view_args")),
        "args": _stringify_payload(request_data.get("args")),
        "form": _stringify_payload(request_data.get("form")),
        "json": _stringify_payload(request_data.get("json")),
    }

    details_text = doc.get("details")
    if isinstance(details_text, (dict, list)):
        try:
            details_text = json.dumps(details_text, ensure_ascii=False, default=str)
        except Exception:
            details_text = str(details_text)
    elif details_text is not None:
        details_text = str(details_text)

    return {
        "id": str(doc.get("_id")),
        "timestamp": timestamp_display,
        "timestamp_iso": timestamp_iso,
        "relative_minutes": rel_minutes,
        "action": {
            "method": method,
            "path": path,
            "remote_addr": remote_addr,
            "user_agent": _extract_user_agent(),
        },
        "by": by,
        "session_id": session_id,
        "details": details_text,
        "request_meta": request_meta,
    }

def get_admin_activity(page=1, per_page=20, query=None):
    """Return formatted admin activity logs with pagination."""
    skip = (page - 1) * per_page
    cursor = (
        mongo.admin_logs.find(query or {})
        .sort("_id", -1)
        .skip(skip)
        .limit(per_page)
    )
    return [_format_log_entry(doc) for doc in cursor]


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
        _log_admin_event(
            "stats_view",
            page=page,
            per_page=per_page,
            total_count=total_count,
        )
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
        _log_admin_event("stats_view_error", reason=str(e))
        flash_message("An error occurred while loading statistics.", "danger")
        return redirect(url_for("admin.admin_dashboard"))

@admin_bp.route("/manual/")
def manual():
    _log_admin_event("manual_index_view")
    return render_template("manuals/index.html")

@admin_bp.route("/manual/<path:page>")
def manual_page(page):
    _log_admin_event("manual_page_view", page=page)
    return render_template(f"manuals/{page}.html")

@admin_bp.route("/logs")
@login_required
@admin_required
@permission_required("VIEW_LOGS")
def logs():
    user_cursor = (
        mongo.users.find({}, {"displayname": 1, "username": 1})
        .sort("username", 1)
        .limit(500)
    )
    users = [
        {
            "id": str(doc["_id"]),
            "name": doc.get("displayname") or doc.get("username") or "Unknown",
        }
        for doc in user_cursor
    ]

    method_set = set(filter(None, mongo.admin_logs.distinct("request.method")))
    method_set.update(filter(None, mongo.admin_logs.distinct("action.method")))
    action_types = sorted(method_set)

    _log_admin_event("admin_logs_view")
    return render_template(
        f"{_ADMIN_TEMPLATE_FOLDER}logs.html",
        users=users,
        action_types=action_types,
    )


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
        filters = {
            "user": request.args.get("user"),
            "start_date": request.args.get("start_date"),
            "end_date": request.args.get("end_date"),
            "action_type": request.args.get("action_type"),
        }
        query = _build_logs_query(filters)
        logs = get_admin_activity(page, per_page, query)
        total_logs = mongo.admin_logs.count_documents(query)
        total_pages = (total_logs + per_page - 1) // per_page

    except Exception as e:
        logger.error(e)
        _log_admin_event("admin_logs_api_error", reason=str(e))
        raise Exception from e

    _log_admin_event(
        "admin_logs_api",
        page=page,
        per_page=per_page,
        filters=_json_safe(filters),
    )
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
    _log_admin_event("analytics_overview_view")
    return demo_analytics()


def demo_analytics():
    """ """
    data = get_demo_views()
    data = count_per_demo(data)

    return render_template(f"{_ADMIN_TEMPLATE_FOLDER}analytics.html", data=data)



from datetime import timedelta
@admin_bp.route("/per_demo_analytics/<demo_id>")
def demo_analytics(demo_id):
    from mielenosoitukset_fi.utils.classes import Demonstration
    try:
        demo_oid = ObjectId(demo_id)
    except Exception:
        _log_admin_event("demo_analytics_detail_error", demo_id=demo_id, reason="invalid_id")
        abort(404, "Invalid demo ID")

    anal = get_per_demo_anal(demo_oid)
    if not anal:
        _log_admin_event("demo_analytics_detail_error", demo_id=demo_id, reason="missing_data")
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
        hour_key = f"{hour:02d}"
        hour_data = day_data.get(hour_key) or day_data.get(str(hour)) or {}
        for minute in range(60):
            minute_key = f"{minute:02d}"
            count = hour_data.get(minute_key)
            if count is None:
                count = hour_data.get(str(minute), 0)
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
    _log_admin_event("demo_analytics_detail_view", demo_id=demo_id)
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
    _log_admin_event("recommendations_api_called", count=len(recommendations))
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

    _log_admin_event("demos_nousussa_requested", limit=limit, returned=len(demo_views))
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


    _log_admin_event("analytics_overall_24h_view", interval=interval)
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

    _log_admin_event("analytics_overall_24h_api", interval=interval, data_points=len(labels))
    return jsonify({
        "labels": labels,
        "data": data,
        "interval": interval
    })
