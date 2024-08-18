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

# User control panel with pagination
@admin_user_bp.route('/')
@login_required
@admin_required
def user_control():
    """Render the user control panel with a list of users."""
    search_query = request.args.get('search', '')
    #page = int(request.args.get('page', 1))
    #per_page = 10

    if search_query:
        users_cursor = mongo.users.find({
            "$or": [
                {"username": {"$regex": search_query, "$options": "i"}},
                {"email": {"$regex": search_query, "$options": "i"}},
            ]
        })
    else:
        users_cursor = mongo.users.find()

    #total_users = users_cursor.count()
    #users = users_cursor.skip((page - 1) * per_page).limit(per_page)
    
    #pagination = {"page": page, "per_page": per_page, "total": total_users}
    
    return render_template('admin_user_control.html', users=users_cursor, search_query=search_query)#, pagination=pagination,)

# Edit user
@admin_user_bp.route('/edit_user/<user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    """Edit user details."""
    user = mongo.users.find_one({"_id": ObjectId(user_id)})
    organizations = mongo.organizations.find()

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        role = request.form.get('role')
        organization_ids = request.form.getlist('organizations')

        # SECURITY: Ensure that only authorized users can update other users' details.
        # Validation for user input
        if not username or not email:
            flash('Username and email are required.')
            return redirect(url_for('admin_user.edit_user', user_id=user_id))
        
        # Validate email format
        if '@' not in email or '.' not in email.split('@')[-1]:
            flash('Invalid email format.')
            return redirect(url_for('admin_user.edit_user', user_id=user_id))

        mongo.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {
                "username": username,
                "email": email,
                "role": role,
                "organizations": [ObjectId(org_id) for org_id in organization_ids]
            }}
        )
        flash('User updated successfully.')
        return redirect(url_for('admin_user.user_control'))

    return render_template('edit_user.html', user=user, organizations=organizations)

# Save user details (if needed separately)
@admin_user_bp.route('/save_user/<user_id>', methods=['POST'])
@login_required
@admin_required
def save_user(user_id):
    """Save updated user details."""
    user = mongo.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        flash('User not found.')
        return redirect(url_for('admin_user.user_control'))

    username = request.form.get('username')
    email = request.form.get('email')
    role = request.form.get('role')
    organization_ids = request.form.getlist('organizations')

    # SECURITY: Ensure that only authorized users can update other users' details.
    # Validation for user input
    if not username or not email:
        flash('Username and email are required.')
        return redirect(url_for('admin_user.edit_user', user_id=user_id))
    
    # Validate email format
    if '@' not in email or '.' not in email.split('@')[-1]:
        flash('Invalid email format.')
        return redirect(url_for('admin_user.edit_user', user_id=user_id))

    mongo.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "username": username,
            "email": email,
            "role": role,
            "organizations": [ObjectId(org_id) for org_id in organization_ids]
        }}
    )
    flash('User updated successfully.')
    return redirect(url_for('admin_user.user_control'))

# Delete user
@admin_user_bp.route('/delete_user/<user_id>', methods=['POST'])  # Changed to use POST method for deletion
@login_required
@admin_required
def delete_user(user_id):
    """Delete a user from the database."""
    user = mongo.users.find_one({"_id": ObjectId(user_id)})

    if user is None:
        flash('User not found.')
        return redirect(url_for('admin_user.user_control'))

    if 'confirm_delete' in request.form:
        # Handle confirmation step
        mongo.users.delete_one({"_id": ObjectId(user_id)})
        flash('User deleted successfully.')
    else:
        flash('User deletion not confirmed.')

    return redirect(url_for('admin_user.user_control'))

# Add confirmation step before deletion
@admin_user_bp.route('/confirm_delete_user/<user_id>', methods=['GET'])
@login_required
@admin_required
def confirm_delete_user(user_id):
    """Render a confirmation page before deleting a user."""
    user = mongo.users.find_one({"_id": ObjectId(user_id)})
    if user is None:
        flash('User not found.')
        return redirect(url_for('admin_user.user_control'))

    return render_template('confirm_delete_user.html', user=user)