import os
import json
import logging
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_file,
)
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from bson.objectid import ObjectId
from wrappers import admin_required, permission_required
from database_manager import DatabaseManager
from auth.models import User  # Import User model

# Constants
LOG_FILE_PATH = "app.log"

# Blueprint setup
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# Initialize MongoDB and Flask-Login
db_manager = DatabaseManager().get_instance()
mongo = db_manager.get_db()

login_manager = LoginManager()
login_manager.login_view = "auth.login"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# User loader function
@login_manager.user_loader
def load_user(user_id):
    """Load a user from the database using their ID."""
    user_doc = mongo.users.find_one({"_id": ObjectId(user_id)})
    return User.from_db(user_doc) if user_doc else None

# Admin logout route
@admin_bp.route("/logout")
@login_required
def admin_logout():
    """Handle admin logout and log the action."""
    username = current_user.username
    logout_user()
    logger.info(f"User {username} logged out successfully.")
    return redirect(url_for("auth.login"))

# Admin dashboard
@admin_bp.route("/dashboard")
@login_required
@admin_required
def admin_dashboard():
    """Render the admin dashboard."""
    return render_template("admin/dashboard.html")

# Admin statistics page
@admin_bp.route("/stats")
@login_required
@admin_required
def stats():
    """Render statistics page with user and organization data."""
    total_users = mongo.users.count_documents({})
    active_users = mongo.users.count_documents({"confirmed": True})
    total_organizations = mongo.organizations.count_documents({})
    
    # Count users by role
    role_counts = get_user_role_counts()

    # Render statistics template
    return render_template(
        "admin/stats.html",
        total_users=total_users,
        total_organizations=total_organizations,
        role_counts=role_counts,
        active_users=active_users,
    )

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

        marquee_config.update({
            "message": new_message,
            "style": f"background-color: {background_color}; padding: 0px !important;",
            "h2_style": f"color: {text_color};",
        })

        # Save updated marquee configuration
        with open(config_file, "w") as f:
            json.dump(marquee_config, f, indent=4)

        flash("Marquee message updated successfully!", "success")
        logger.info("Marquee message updated to: %s", new_message)

        return redirect(url_for("admin.manage_marquee"))

    return render_template(
        "admin/manage_marquee.html",
        current_message=marquee_config["message"],
        background_color=marquee_config["style"].split(": ")[1].split(";")[0],
        text_color=marquee_config["h2_style"].split(": ")[1],
    )
