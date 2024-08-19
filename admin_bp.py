from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from bson.objectid import ObjectId
from administration import admin_required
from database_manager import DatabaseManager
from models import User  # Import User model
import logging

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Initialize MongoDB
db_manager = DatabaseManager()
mongo = db_manager.get_db()

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'admin.admin_login'

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
@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user_doc = mongo.users.find_one({"username": username})

        if user_doc:
            user = User.from_db(user_doc)
            if user.check_password(password):
                login_user(user)
                logger.info(f"User {username} logged in successfully.")
                return redirect(url_for('admin.admin_dashboard'))

        logger.warning(f"Failed login attempt for username: {username}")
        flash('Invalid credentials')  # Log invalid credentials attempt for security audit

    return render_template('admin_login.html')

# Admin logout route
@admin_bp.route('/logout')
@login_required
def admin_logout():
    username = current_user.username
    logout_user()
    logger.info(f"User {username} logged out successfully.")
    return redirect(url_for('admin.admin_login'))

# Admin dashboard
@admin_bp.route('/dashboard')
@login_required
@admin_required
def admin_dashboard():
    pending_demos = mongo.demonstrations.find({"approved": False})
    pending_orgs = mongo.organizations.find({"verified": False})  # Fetch pending organizations
    return render_template('admin_dashboard.html', pending_demos=pending_demos, pending_orgs=pending_orgs)

# DEMONSTRATIONAL ADMINISM

# Approve demonstration
@admin_bp.route('/approve/demo/<demo_id>')
@login_required
@admin_required
def approve_demo(demo_id):
    # SECURITY: Ensure that only authorized admin can approve demonstrations.
    mongo.demonstrations.update_one(
        {"_id": ObjectId(demo_id)},
        {"$set": {"approved": True}}
    )
    logger.info(f"Demo {demo_id} approved by admin {current_user.username}")
    flash('Demonstration approved.')
    return redirect(url_for('admin.admin_dashboard'))

# Reject demonstration
@admin_bp.route('/reject/demo/<demo_id>')
@login_required
@admin_required
def reject_demo(demo_id):
    # SECURITY: Ensure that only authorized admin can reject demonstrations.
    mongo.demonstrations.delete_one({"_id": ObjectId(demo_id)})
    logger.info(f"Demo {demo_id} rejected by admin {current_user.username}")
    flash('Demonstration rejected.')
    return redirect(url_for('admin.admin_dashboard'))

# ORGANIZATIONAL ADMINISM

# Approve organization
@admin_bp.route('/approve/org/<org_id>')
@login_required
@admin_required
def approve_org(org_id):
    # SECURITY: Ensure that only authorized admin can approve organizations.
    mongo.organizations.update_one(
        {"_id": ObjectId(org_id)},
        {"$set": {"verified": True}}
    )
    logger.info(f"Organization {org_id} approved by admin {current_user.username}")
    flash('Organization approved.')
    return redirect(url_for('admin.admin_dashboard'))

# Reject organization
@admin_bp.route('/reject/org/<org_id>')
@login_required
@admin_required
def reject_org(org_id):
    # SECURITY: Ensure that only authorized admin can reject organizations.
    mongo.organizations.delete_one({"_id": ObjectId(org_id)})
    logger.info(f"Organization {org_id} rejected by admin {current_user.username}")
    flash('Organization rejected.')
    return redirect(url_for('admin.admin_dashboard'))