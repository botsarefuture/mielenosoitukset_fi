from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from bson.objectid import ObjectId
from database_manager import DatabaseManager
from administration import admin_required
from models import User  # Import User model

from emailer.EmailSender import EmailSender
email_sender = EmailSender()

admin_user_bp = Blueprint('admin_user', __name__, url_prefix='/admin/user')

# Initialize MongoDB
db_manager = DatabaseManager()
mongo = db_manager.get_db()

def flash_message(message, category):
    """Flash a message with a specific category."""
    categories = {
        'info': 'info',
        'approved': 'success',
        'warning': 'warning',
        'error': 'danger'
    }
    flash(message, categories.get(category, 'info'))

# User control panel with pagination
@admin_user_bp.route('/')
@login_required
@admin_required
def user_control():
    """Render the user control panel with a list of users."""
    search_query = request.args.get('search', '')

    if search_query:
        users_cursor = mongo.users.find({
            "$or": [
                {"username": {"$regex": search_query, "$options": "i"}},
                {"email": {"$regex": search_query, "$options": "i"}},
            ]
        })
    else:
        users_cursor = mongo.users.find()
    
    return render_template('admin/user/list.html', users=users_cursor, search_query=search_query)

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
        confirmed = request.form.get('confirmed', False)

        # SECURITY: Ensure that only authorized users can update other users' details.
        # Validation for user input
        if not username or not email:
            flash_message('Käyttäjänimi ja sähköposti ovat pakollisia.', 'error')
            return redirect(url_for('admin_user.edit_user', user_id=user_id))
        
        # Validate email format
        if '@' not in email or '.' not in email.split('@')[-1]:
            flash_message('Virheellinen sähköpostimuoto.', 'error')
            return redirect(url_for('admin_user.edit_user', user_id=user_id))

        orgs = []

        for organization in organization_ids:
            orgs.append({"org_id": organization, "role": "admin"})
        
        if confirmed:
            confirmed = True
        
        mongo.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {
                "username": username,
                "email": email,
                "role": role,
                "organizations": orgs,  # FIXME: Organizations should be a list like this [{"org_id": id_of_org, "role": role_in_org}]
                "confirmed": confirmed
            }}
        )
        
        flash_message('Käyttäjä päivitetty onnistuneesti.', 'approved')
        return redirect(url_for('admin_user.user_control'))
    
    org_ids = [org["org_id"] for org in user["organizations"]]
    
    user["org_ids"] = org_ids
        
    return render_template('admin/user/edit.html', user=user, organizations=organizations, org_ids=org_ids)

@admin_user_bp.route('/save_user/<user_id>', methods=['POST'])
@login_required
@admin_required
def save_user(user_id):
    """Save updated user details and send email notification."""
    user = mongo.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        flash_message('Käyttäjää ei löydy.', 'error')
        return redirect(url_for('admin_user.user_control'))

    username = request.form.get('username')
    email = request.form.get('email')
    role = request.form.get('role')
    organization_ids = request.form.getlist('organizations')
    confirmed = request.form.get('confirmed', False)

    # SECURITY: Ensure that only authorized users can update other users' details.
    # Validation for user input
    if not username or not email:
        flash_message('Käyttäjänimi ja sähköposti ovat pakollisia.', 'error')
        return redirect(url_for('admin_user.edit_user', user_id=user_id))
    
    # Validate email format
    if '@' not in email or '.' not in email.split('@')[-1]:
        flash_message('Virheellinen sähköpostimuoto.', 'error')
        return redirect(url_for('admin_user.edit_user', user_id=user_id))
    
    if confirmed:
        confirmed = True

    # Retrieve organization names based on IDs
    organizations = mongo.organizations.find({"_id": {"$in": [ObjectId(org_id) for org_id in organization_ids]}})
    org_names = [org['name'] for org in organizations]

    # Update user details
    mongo.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "username": username,
            "email": email,
            "role": role,
            "organizations": [{"org_id": org_id, "role": "admin"} for org_id in organization_ids],  # Update user organizations
            "confirmed": confirmed
        }}
    )

    # Send email notification
    email_sender.queue_email(
        template_name='user_update_notification.html',
        subject='Tilisi tiedot on päivitetty',
        recipients=[email],
        context={
            'user_name': username,
            'role': role,
            'organization_names': ', '.join(org_names),
            'action': 'päivitetty'  # or 'added'/'revoked' based on your logic
        }
    )

    flash_message('Käyttäjä päivitetty onnistuneesti.', 'approved')
    return redirect(url_for('admin_user.user_control'))

# Delete user
@admin_user_bp.route('/delete_user/<user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """Delete a user from the database."""
    user = mongo.users.find_one({"_id": ObjectId(user_id)})

    if user is None:
        flash_message('Käyttäjää ei löydy.', 'error')
        return redirect(url_for('admin_user.user_control'))

    if 'confirm_delete' in request.form:
        # Handle confirmation step
        mongo.users.delete_one({"_id": ObjectId(user_id)})
        flash_message('Käyttäjä poistettu onnistuneesti.', 'approved')
    else:
        return redirect(url_for('admin_user.confirm_delete_user', user_id=user["_id"]))

    return redirect(url_for('admin_user.user_control'))

# Add confirmation step before deletion
@admin_user_bp.route('/confirm_delete_user/<user_id>', methods=['GET'])
@login_required
@admin_required
def confirm_delete_user(user_id):
    """Render a confirmation page before deleting a user."""
    user = mongo.users.find_one({"_id": ObjectId(user_id)})
    if user is None:
        flash_message('Käyttäjää ei löydy.', 'error')
        return redirect(url_for('admin_user.user_control'))

    return render_template('admin/user/confirm.html', user=user)
