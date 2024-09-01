from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required
from auth.models import User
import jwt
import datetime
from emailer.EmailSender import EmailSender
from database_manager import DatabaseManager

db_manager = DatabaseManager()
mongo = db_manager.get_db()

email_sender = EmailSender()
auth_bp = Blueprint('auth', __name__, template_folder="./templates/")

def verify_emailer(email, username):
    token = generate_confirmation_token(email)
    confirmation_url = url_for('auth.confirm_email', token=token, _external=True)
    
    email_sender.queue_email(
                template_name='registration_confirmation_email.html',
                subject='Confirm Your Registration',
                recipients=[email],
                context={
                    'confirmation_url': confirmation_url,
                    'user_name': username
                }
            )

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')

        if not username or not password or len(username) < 3 or len(password) < 6:
            flash('Invalid input. Username must be at least 3 characters and password at least 6 characters.', "error")
            return redirect(url_for('auth.register'))

        if mongo.users.find_one({"username": username}):
            flash('Username already exists.', 'warning')
            return redirect(url_for('auth.register'))

        if mongo.users.find_one({"email": email}):
            flash('Email is already registered. Login instead.', "warning")
            return redirect(url_for('auth.login'))

        user_data = User.create_user(username, password, email)
        mongo.users.insert_one(user_data)

        try:
            verify_emailer(email, username)
            flash('Registration successful! Please check your email to confirm your account.', "info")
        except Exception as e:
            flash(f'Error sending confirmation email: {e}', "error")

        return redirect(url_for('auth.login'))

    return render_template('register.html')

@auth_bp.route('/confirm_email/<token>')
def confirm_email(token):
    email = verify_confirmation_token(token)
    if email:
        user = mongo.users.find_one({"email": email})
        if user:
            mongo.users.update_one({"email": email}, {"$set": {"confirmed": True}})
            flash('Your email has been confirmed. You can now log in.', 'info')
        else:
            flash('User not found.', 'error')
    else:
        flash('The confirmation link is invalid or has expired.', 'warning')

    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Please enter both username and password.', 'warning')
            return redirect(url_for('auth.login'))

        user_doc = mongo.users.find_one({"username": username})

        if not user_doc:
            flash(f"Käyttäjänimellä '{username}' ei löytynyt käyttäjiä.", 'error')
            return redirect(url_for('auth.login'))
        
        user = User.from_db(user_doc)
        if user.check_password(password) == False:
            flash(f"Käyttäjänimi tai salasana on väärin.", "error")
            return redirect(url_for('auth.login')) 
        
        if user.confirmed:
            login_user(user)
            return redirect(url_for('index'))
        
        else:
            flash("Sähköpostiosoitettasi ei ole vahvistettu. Tarkista sähköpostisi.")
            verify_emailer(user.email, username)
            return redirect(url_for('index'))
                        

    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Kirjauduit onnistuneesti ulos')
    return redirect(url_for('auth.login'))

@auth_bp.route('/password_reset_request', methods=['GET', 'POST'])
def password_reset_request():
    if request.method == 'POST':
        email = request.form.get('email')
        user = mongo.users.find_one({"email": email})

        if user:
            token = generate_reset_token(email)
            reset_url = url_for('auth.password_reset', token=token, _external=True)

            try:
                email_sender.queue_email(
                    template_name='password_reset_email.html',
                    subject='Password Reset Request',
                    recipients=[email],
                    context={
                        'reset_url': reset_url,
                        'user_name': user.get('username')
                    }
                )
                flash('A password reset link has been sent to your email address.', 'info')
            except Exception as e:
                flash(f'Error sending password reset email: {e}', 'error')
                
            return redirect(url_for('auth.login'))

        flash('No account found with that email address.', 'info')
        return redirect(url_for('auth.password_reset_request'))

    return render_template('password_reset_request.html')

@auth_bp.route('/password_reset/<token>', methods=['GET', 'POST'])
def password_reset(token):
    email = verify_reset_token(token)
    if not email:
        flash('The password reset link is invalid or has expired.', 'warning')
        return redirect(url_for('auth.password_reset_request'))

    if request.method == 'POST':
        password = request.form.get('password')
        
        user_doc = mongo.users.find_one({"email": email})
        if not user_doc:
            flash('User not found.', 'warning')
            return redirect(url_for('auth.password_reset_request'))

        user = User.from_db(user_doc)
        user.change_password(mongo, password)
        
        flash('Your password has been updated successfully.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('password_reset.html', token=token)

def generate_reset_token(email):
    return jwt.encode({
        'email': email,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }, current_app.config['SECRET_KEY'], algorithm='HS256')

def verify_reset_token(token):
    try:
        data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        return data['email']
    except Exception:
        return None

def generate_confirmation_token(email):
    return jwt.encode({
        'email': email,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }, current_app.config['SECRET_KEY'], algorithm='HS256')

def verify_confirmation_token(token):
    try:
        data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        return data['email']
    except Exception:
        return None
