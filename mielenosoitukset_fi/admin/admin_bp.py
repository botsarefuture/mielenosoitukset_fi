import json
from mielenosoitukset_fi.utils.logger import logger

import os
import warnings

from bson.objectid import ObjectId
from flask import (
    Blueprint,
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
from .utils import AdminActParser, log_admin_action_V2

# Constants
LOG_FILE_PATH = "app.log"

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
            log_admin_action_V2(AdminActParser().log_request_info(request.__dict__, current_user))
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
    return render_template("admin/dashboard.html")


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
            "admin/stats.html",
            total_users=total_users,
            total_organizations=total_organizations,
            role_counts=role_counts,
            active_users=active_users,
            data=data
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
    return render_template("admin/logs.html")

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


# Route for managing the marquee message
@admin_bp.route("/manage-marquee", methods=["GET", "POST"])
@login_required
@admin_required
@permission_required("MANAGE_MARQUEE")
def manage_marquee():
    """Manage the marquee message displayed on the site."""
    config_file = "marquee_config.json"

    # Load existing marquee configuration
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            marquee_config = json.load(f)
    else:
        marquee_config = {
            "message": "",
            "default_message": "NO",
            "style": "background-color: var(--background-color); padding: 0px !important;",
            "h2_style": "color: var(--primary-color);",
        }

    if request.method == "POST":
        # Update marquee configuration based on user input
        new_message = request.form.get("marquee_message", "").strip()
        background_color = request.form.get("background_color", "#ffffff")
        text_color = request.form.get("text_color", "#000000")

        marquee_config.update(
            {
                "message": new_message,
                "style": f"background-color: {background_color}; padding: 0px !important;",
                "h2_style": f"color: {text_color};",
            }
        )

        # Save updated marquee configuration
        with open(config_file, "w") as f:
            json.dump(marquee_config, f, indent=4)

        flash_message("Marquee message updated successfully!", "success")
        logger.info("Marquee message updated to: %s", new_message)

        return redirect(url_for("admin.manage_marquee"))

    return render_template(
        "admin/manage_marquee.html",
        current_message=marquee_config["message"],
        background_color=marquee_config["style"].split(": ")[1].split(";")[0],
        text_color=marquee_config["h2_style"].split(": ")[1],
    )


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

    return render_template("admin/analytics.html", data=data)


def send_red_alert_email(user):
    """Send a red alert email to the user.

    Parameters
    ----------
    user :


    Returns
    -------


    """
    # Use email_sender
    from emailer import EmailSender

    email_sender = EmailSender()
    email_sender.queue_email(
        template_name="red_alert_email.html",
        subject="Red Alert",
        recipients=[user.email],
        context={"username": user.username},
    )


def initiate_red_alert():
    """Initiate a red alert."""
    # 1. Send email to all admins
    # 2. Log the red alert
    # 3. Implement your red alert logic here

    # 1. Send email to all admins
    admins = mongo.users.find(
        {"role": {"$in": ["admin", "global_admin"]}}
    )  # Assuming the role is "admin" or "global_admin"

    for admin in admins:
        send_red_alert_email(admin)

    # 2. Log the red alert
    logger.critical("Red alert initiated")

    # 3. Marquee should show the red alert
    with open("marquee_config.json", "r") as f:
        marquee_config = json.load(f)
        marquee_config["message"] = "RED ALERT "
        marquee_config["style"] = "background-color: red; padding: 0px !important;"
        marquee_config["h2_style"] = "color: white;"

    with open("marquee_config.json", "w") as f:
        json.dump(marquee_config, f, indent=4)

    return "Red alert initiated"


@admin_bp.route("/shutdown", methods=["POST"])
@login_required
@admin_required
@permission_required("SHUTDOWN_SERVER")
def shutdown():
    """Shutdown the server securely."""
    if not current_user.has_role("admin"):
        logger.warning(f"Unauthorized shutdown attempt by user {current_user.username}")
        mongo.users.update_one({"_id": current_user.id}, {"$set": {"banned": True}})
        initiate_red_alert()
        return "Unauthorized", 403

    logger.info(f"Server shutdown initiated by user {current_user.username}")
    os.system("shutdown -h now")
    return "Server shutting down..."


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
