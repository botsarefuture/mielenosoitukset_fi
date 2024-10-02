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

LOG_FILE_PATH = "app.log"

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# Initialize MongoDB
db_manager = DatabaseManager().get_instance()
mongo = db_manager.get_db()

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.login_view = "admin.admin_login"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# User loader function
@login_manager.user_loader
def load_user(user_id):
    user_doc = mongo.users.find_one({"_id": ObjectId(user_id)})
    if user_doc:
        return User.from_db(user_doc)
    return None

# LOGIN & LOGOUT

# Admin login route
@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user_doc = mongo.users.find_one({"username": username})

        if user_doc:
            user = User.from_db(user_doc)
            if user.check_password(password):
                login_user(user)
                logger.info(f"User {username} logged in successfully.")
                return redirect(url_for("admin.admin_dashboard"))

        logger.warning(f"Failed login attempt for username: {username}")
        flash("Invalid credentials")

    return render_template("admin/auth/login.html")

# Admin logout route
@admin_bp.route("/logout")
@login_required
def admin_logout():
    username = current_user.username
    logout_user()
    logger.info(f"User {username} logged out successfully.")
    return redirect(url_for("admin.admin_login"))

# Admin dashboard
@admin_bp.route("/dashboard")
@login_required
@admin_required
def admin_dashboard():
    return render_template("admin/dashboard.html")

@admin_bp.route("/settings", methods=["GET", "POST"])
@login_required
@admin_required
def settings():
    """Render settings page and handle settings submission."""
    if request.method == "POST":
        # Handle form data submission here
        site_name = request.form.get("site_name")
        admin_email = request.form.get("admin_email")
        site_description = request.form.get("site_description")

        # Here you would normally save these settings to the database
        # For example:
        mongo.settings.update_one(
            {"_id": ObjectId("your_settings_id")},  # Use your settings document ID
            {
                "$set": {
                    "site_name": site_name,
                    "admin_email": admin_email,
                    "site_description": site_description,
                }
            }
        )

        flash("Asetukset on tallennettu onnistuneesti.", "success")
        return redirect(url_for("admin.settings"))

    # Render the settings page
    return render_template("admin/settings.html")

@admin_bp.route("/stats")
@login_required
@admin_required
def stats():
    """Render statistics page with user and organization data."""
    
    # Fetch total number of users
    total_users = mongo.users.count_documents({})
    
    active_users = mongo.users.count_documents({"confirmed": True})

    # Fetch total number of organizations
    total_organizations = mongo.organizations.count_documents({})
    
    # Fetch active users (you can customize this as per your criteria)
    
    # Example: Get the number of users per role
    user_roles = mongo.users.aggregate([
        {
            "$group": {
                "_id": "$role",
                "count": {"$sum": 1}
            }
        }
    ])
    
    role_counts = {role["_id"]: role["count"] for role in user_roles}

    # Pass the statistics to the template
    return render_template(
        "admin/stats.html",
        total_users=total_users,
        total_organizations=total_organizations,
        role_counts=role_counts,
        active_users = active_users
    )

# Admin help
@admin_bp.route("/help")
@login_required
@admin_required
def help():
    return render_template("admin/help.html")  # Ensure you create this template
