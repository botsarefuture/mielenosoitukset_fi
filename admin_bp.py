from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from bson.objectid import ObjectId
from administration import admin_required
from database_manager import DatabaseManager
from models import User  # Import User model

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Initialize MongoDB
db_manager = DatabaseManager()
mongo = db_manager.get_db()

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'admin.admin_login'

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

        if user_doc and User.check_password(user_doc['password_hash'], password):  # Use hashed passwords
            user = User.from_db(user_doc)
            login_user(user)
            return redirect(url_for('admin.admin_dashboard'))

        flash('Invalid credentials')

    return render_template('admin_login.html')

# Admin logout route
@admin_bp.route('/logout')
@login_required
def admin_logout():
    logout_user()
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
    mongo.demonstrations.update_one(
        {"_id": ObjectId(demo_id)},
        {"$set": {"approved": True}}
    )
    flash('Demonstration approved.')
    return redirect(url_for('admin.admin_dashboard'))

# Reject demonstration
@admin_bp.route('/reject/demo/<demo_id>')
@login_required
@admin_required
def reject_demo(demo_id):
    mongo.demonstrations.delete_one({"_id": ObjectId(demo_id)})
    flash('Demonstration rejected.')
    return redirect(url_for('admin.admin_dashboard'))

# ORGANIZATIONAL ADMINISM

# Approve organization
@admin_bp.route('/approve/org/<org_id>')
@login_required
@admin_required
def approve_org(org_id):
    mongo.organizations.update_one(
        {"_id": ObjectId(org_id)},
        {"$set": {"verified": True}}
    )
    flash('Organization approved.')
    return redirect(url_for('admin.admin_dashboard'))

# Reject organization
@admin_bp.route('/reject/org/<org_id>')
@login_required
@admin_required
def reject_org(org_id):
    mongo.organizations.delete_one({"_id": ObjectId(org_id)})
    flash('Organization rejected.')
    return redirect(url_for('admin.admin_dashboard'))
