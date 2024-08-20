from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user

def permission_needed(permission, organization_id=None):
    """
    Decorator that checks if the current user has a specific permission within a given organization.
    
    :param permission: The required permission (e.g., 'edit_events').
    :param organization_id: The organization ID to check the permission for. If not provided, the default organization will be used.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Ensure the user is authenticated
            if not current_user.is_authenticated:
                flash('You need to log in to access this page.')
                return redirect(url_for('auth.login'))  # Redirect to the login page if not authenticated
            
            # If the user is a global admin, grant access regardless of specific permissions
            if current_user.global_admin:
                return f(*args, **kwargs)
            
            # If organization_id is provided in kwargs, use it; otherwise, fall back to the parameter
            org_id = kwargs.get('organization_id', organization_id)
            
            # Ensure the user is a member of the organization
            if not org_id or not current_user.is_member_of_organization(org_id):
                flash('You are not a member of this organization.')
                return redirect(url_for('home'))  # Adjust to your desired redirect route
            
            # Check if the user has the required permission in the organization
            if not current_user.has_permission(org_id, permission):
                flash('You do not have permission to access this page.')
                return redirect(url_for('home'))  # Adjust to your desired redirect route
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if current_user is authenticated before checking global_admin status
        if not current_user.is_authenticated:
            flash('You need to log in to access this page.')
            return redirect(url_for('login'))  # Redirect to the login page if not authenticated
        
        if not current_user.global_admin:
            flash('You do not have permission to access this page.')
            return redirect(url_for('admin.admin_login'))  # Adjust to the correct admin login route if necessary

        return f(*args, **kwargs)
    
    return decorated_function