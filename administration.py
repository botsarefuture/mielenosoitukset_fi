from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.global_admin:
            flash('You do not have permission to access this page.')
            return redirect(url_for('admin.admin_login'))
        return f(*args, **kwargs)
    return decorated_function