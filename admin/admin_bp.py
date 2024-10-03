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
from wrappers import admin_required
from database_manager import DatabaseManager
from auth.models import User  # Import User model
import logging

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
    user_doc = mongo.users.find_one({"_id": ObjectId(user_id)})
    return User.from_db(user_doc) if user_doc else None


# Admin logout route
@admin_bp.route("/logout")
@login_required
def admin_logout():
    username = current_user.username
    logout_user()
    logger.info(f"User {username} logged out successfully.")
    return redirect(url_for("auth.login"))


# Admin dashboard
@admin_bp.route("/dashboard")
@login_required
@admin_required
def admin_dashboard():
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
