from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if current_user is authenticated before checking global_admin status
        if not current_user.is_authenticated:
            flash('Sinun täytyy kirjautua sisään käyttääksesi tätä sivua.')
            return redirect(url_for('login'))  # Redirect to the login page if not authenticated
        
        if not current_user.global_admin:
            flash('Sinulla ei ole riittäviä oikeuksia käyttääksesi tätä sivua.')
            return redirect(url_for('admin.admin_login'))  # Adjust to the correct admin login route if necessary

        return f(*args, **kwargs)
    
    return decorated_function