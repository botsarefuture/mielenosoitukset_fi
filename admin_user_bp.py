from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from bson.objectid import ObjectId
from database_manager import DatabaseManager
from administration import admin_required
from models import User  # Import User model

admin_user_bp = Blueprint('admin_user', __name__, url_prefix='/admin/user')

# Initialize MongoDB
db_manager = DatabaseManager()
mongo = db_manager.get_db()

# User control panel
@admin_user_bp.route('/')
@login_required
@admin_required
def user_control():

    users = mongo.users.find()
    return render_template('admin_user_control.html', users=users)

# Edit user
@admin_user_bp.route('/edit_user/<user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):

    user = mongo.users.find_one({"_id": ObjectId(user_id)})
    organizations = mongo.organizations.find()
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        role = request.form.get('role')
        organization_ids = request.form.getlist('organizations')
        
        # Update user details
        mongo.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {
                "username": username,
                "email": email,
                "role": role,
                "organizations": [ObjectId(org_id) for org_id in organization_ids]
            }}
        )
        flash('Käyttäjä päivitetty.')
        return redirect(url_for('admin_user.user_control'))
    
    return render_template('edit_user.html', user=user, organizations=organizations)

# Save user details (if needed separately)
@admin_user_bp.route('/save_user/<user_id>', methods=['POST'])
@login_required
@admin_required
def save_user(user_id):

    user = mongo.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        flash('Käyttäjää ei löytynyt.')
        return redirect(url_for('admin.user_control'))
    
    username = request.form.get('username')
    email = request.form.get('email')
    role = request.form.get('role')
    organization_ids = request.form.getlist('organizations')

    mongo.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "username": username,
            "email": email,
            "role": role,
            "organizations": [ObjectId(org_id) for org_id in organization_ids]
        }}
    )
    flash('Käyttäjä päivitetty.')
    return redirect(url_for('admin_user.user_control'))

# Delete user
@admin_user_bp.route('/delete_user/<user_id>')
@login_required
@admin_required
def delete_user(user_id):

    mongo.users.delete_one({"_id": ObjectId(user_id)})
    flash('Käyttäjä poistettu.')
    return redirect(url_for('admin_user.user_control'))
