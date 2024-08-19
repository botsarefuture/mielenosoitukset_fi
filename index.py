from flask import Flask, render_template, request, redirect, url_for, flash
from bson.objectid import ObjectId
from classes import Organizer, Demonstration
from database_manager import DatabaseManager
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required
from models import User  # Import User model
import jwt  # For generating tokens
import datetime
from emailer.EmailSender import EmailSender
email_sender = EmailSender()

app = Flask(__name__)
app.config.from_object('config.Config')

MAINTANENCE = False

@app.before_request
def is_maintanence():
    if MAINTANENCE:
        return render_template("maintanence.html")

# Initialize MongoDB
db_manager = DatabaseManager()
mongo = db_manager.get_db()

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Redirect to login view if not authenticated

# User Loader function
@login_manager.user_loader
def load_user(user_id):
    """
    Load a user from the database by user_id.
    """
    user_doc = mongo.users.find_one({"_id": ObjectId(user_id)})
    if user_doc:
        return User.from_db(user_doc)
    return None

# Import and register blueprints
from admin_bp import admin_bp
app.register_blueprint(admin_bp)

from organization import organization_bp
app.register_blueprint(organization_bp)

from admin_user_bp import admin_user_bp
app.register_blueprint(admin_user_bp)

from admin_org_bp import admin_org_bp
app.register_blueprint(admin_org_bp)

from admin_demo_bp import admin_demo_bp
app.register_blueprint(admin_demo_bp)


@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Handle user registration.
    """
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')

        # Validation for username and password
        if not username or not password or len(username) < 3 or len(password) < 6:
            flash('Invalid input. Username must be at least 3 characters and password at least 6 characters.')
            return redirect(url_for('register'))

        # Check if the username already exists
        if mongo.users.find_one({"username": username}):
            flash('Username already exists.')
            return redirect(url_for('register'))

        user_data = User.create_user(username, password, email)
        mongo.users.insert_one(user_data)

        flash('User registered successfully!')
        return redirect(url_for('login'))

    return render_template('auth/register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handle user login.
    """
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Validation for username and password fields
        if not username or not password:
            flash('Please enter both username and password.')
            return redirect(url_for('login'))

        user_doc = mongo.users.find_one({"username": username})

        if user_doc:
            user = User.from_db(user_doc)
            if user.check_password(password):
                login_user(user)
                return redirect(url_for('index'))

        flash('Invalid username or password.')

    return render_template('auth/login.html')

# Admin logout route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Generate a password reset token
def generate_reset_token(email):
    return jwt.encode({
        'email': email,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)  # Token expires in 1 hour
    }, app.config['SECRET_KEY'], algorithm='HS256')

# Verify the password reset token
def verify_reset_token(token):
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return data['email']
    except Exception as e:
        return None

@app.route('/password_reset_request', methods=['GET', 'POST'])
def password_reset_request():
    if request.method == 'POST':
        email = request.form.get('email')
        user = mongo.users.find_one({"email": email})

        if user:
            token = generate_reset_token(email)
            reset_url = url_for('password_reset', token=token, _external=True)

            # Send the password reset email
            email_sender.queue_email(
                template_name='password_reset_email.html',
                subject='Password Reset Request',
                recipients=[email],
                context={
                    'reset_url': reset_url,
                    'user_name': user.get('username')
                }
            )
            
            flash('A password reset link has been sent to your email address.')
            return redirect(url_for('login'))

        flash('No account found with that email address.')
        return redirect(url_for('password_reset_request'))

    return render_template('auth/password_reset_request.html')
@app.route('/password_reset/<token>', methods=['GET', 'POST'])
def password_reset(token):
    email = verify_reset_token(token)
    if not email:
        flash('The password reset link is invalid or has expired.')
        return redirect(url_for('password_reset_request'))

    if request.method == 'POST':
        password = request.form.get('password')
        
        # Retrieve the user from the database
        user_doc = mongo.users.find_one({"email": email})
        if not user_doc:
            flash('User not found.')
            return redirect(url_for('password_reset_request'))

        # Create a User instance
        user = User.from_db(user_doc)
        
        # Change the user's password
        user.change_password(mongo, password)
        
        flash('Your password has been updated successfully.')
        return redirect(url_for('login'))

    return render_template('auth/password_reset.html', token=token)

@app.route('/')
def index():
    """
    Display the index page with a list of approved demonstrations.
    """
    search_query = request.args.get('search', '')

    # Consider adding pagination to handle large sets of results more efficiently.
    if search_query:
        demonstrations = mongo.demonstrations.find({
            "approved": True,
            "$or": [
                {"title": {"$regex": search_query, "$options": "i"}},
                {"city": {"$regex": search_query, "$options": "i"}},
                {"topic": {"$regex": search_query, "$options": "i"}},
                {"address": {"$regex": search_query, "$options": "i"}}
            ]
        })
    else:
        demonstrations = mongo.demonstrations.find({"approved": True})

    return render_template('index.html', demonstrations=demonstrations)

@app.route('/submit', methods=['GET', 'POST'])
def submit():
    """
    Handle submission of a new demonstration.
    """
    if request.method == 'POST':
        # Get form data
        title = request.form.get('title')
        date = request.form.get('date')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        topic = request.form.get('topic')
        facebook = request.form.get('facebook')
        city = request.form.get('city')
        address = request.form.get('address')
        event_type = request.form.get('type')
        route = request.form.get('route') if event_type == 'marssi' else None

        # Validation for form data
        if not title or not date or not start_time or not end_time or not topic or not city or not address:
            flash('Please fill out all required fields.')
            return redirect(url_for('submit'))

        # Get organizers from the form and create Organizer instances
        organizers = []
        i = 1
        while f'organizer_name_{i}' in request.form:
            organizer = Organizer(
                name=request.form.get(f'organizer_name_{i}'),
                email=request.form.get(f'organizer_email_{i}'),
                website=request.form.get(f'organizer_website_{i}')
            )
            organizers.append(organizer)
            i += 1

        # Create a Demonstration instance
        demonstration = Demonstration(
            title=title,
            date=date,
            start_time=start_time,
            end_time=end_time,
            topic=topic,
            facebook=facebook,
            city=city,
            address=address,
            event_type=event_type,
            route=route,
            organizers=organizers,
            approved=False
        )

        # Save to MongoDB
        mongo.demonstrations.insert_one(demonstration.to_dict())

        flash('Demonstration submitted successfully! It will be reviewed by an admin.')
        return redirect(url_for('index'))

    return render_template('submit.html')

@app.route('/demonstrations')
def demonstrations():
    """
    List all approved demonstrations, optionally filtered by search query.
    """
    search_query = request.args.get('search', '')

    if search_query:
        demonstrations = mongo.demonstrations.find({
            "approved": True,
            "$or": [
                {"title": {"$regex": search_query, "$options": "i"}},
                {"location": {"$regex": search_query, "$options": "i"}},
                {"organizer": {"$regex": search_query, "$options": "i"}}
            ]
        })
    else:
        demonstrations = mongo.demonstrations.find({"approved": True})

    return render_template('list.html', demonstrations=demonstrations)

@app.route('/demonstration/<demo_id>')
def demonstration_detail(demo_id):
    """
    Display details of a specific demonstration.
    """
    demo = mongo.demonstrations.find_one({"_id": ObjectId(demo_id), "approved": True})

    if demo is None:
        flash("Demonstration not found or not approved.")
        return redirect(url_for('demonstrations'))

    return render_template('detail.html', demo=demo)

@app.route('/edit/<demo_id>', methods=['GET', 'POST'])
@login_required
def edit_event(demo_id):
    """
    Handle editing of a demonstration.
    """
    if request.method == 'POST':
        # Get form data
        title = request.form.get('title')
        date = request.form.get('date')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        topic = request.form.get('topic')
        event_type = request.form.get('type')
        route = request.form.get('route') if event_type == 'marssi' else None
        facebook = request.form.get('facebook')
        city = request.form.get('city')
        address = request.form.get('address')

        # Validation for form data
        if not title or not date or not start_time or not end_time or not topic or not city or not address:
            flash('Please fill out all required fields.')
            return redirect(url_for('edit_event', demo_id=demo_id))

        # Get organizers from form data
        organizers = []
        organizer_names = request.form.getlist('organizers[]')
        organizer_websites = request.form.getlist('organizer_websites[]')
        organizer_emails = request.form.getlist('organizer_emails[]')

        for name, website, email in zip(organizer_names, organizer_websites, organizer_emails):
            if name:  # Ensure that the organizer name is not empty
                organizer = Organizer(name=name, website=website, email=email)
                organizers.append(organizer)

        # Update the demonstration in the database
        mongo.demonstrations.update_one(
            {"_id": ObjectId(demo_id)},
            {
                "$set": {
                    'title': title,
                    'date': date,
                    'start_time': start_time,
                    'end_time': end_time,
                    'topic': topic,
                    'type': event_type,
                    'route': route,
                    'facebook': facebook,
                    'city': city,
                    'address': address,
                    'organizers': [org.to_dict() for org in organizers]
                }
            }
        )

        flash('Event updated successfully!')
        return redirect(url_for('demonstration_detail', demo_id=demo_id))

    # GET request - fetch event details
    demo_data = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
    if demo_data is None:
        flash("Event not found.")
        return redirect(url_for('demonstrations'))

    # Convert MongoDB data back to Demonstration object
    demo = Demonstration.from_dict(demo_data)

    return render_template('edit_event.html', demo=demo)

@app.route('/delete/<demo_id>', methods=['POST'])
@login_required
def delete_event(demo_id):
    """
    Handle deletion of a demonstration.
    """
    demo = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})

    if demo is None:
        flash("Event not found.")
        return redirect(url_for('demonstrations'))

    mongo.demonstrations.delete_one({"_id": ObjectId(demo_id)})
    flash('Event deleted successfully!')
    return redirect(url_for('demonstrations'))

if __name__ == '__main__':
    app.run(debug=True)