from flask import Flask, render_template, request, redirect, url_for, flash
from bson.objectid import ObjectId
from classes import Organizer, Demonstration
from database_manager import DatabaseManager
from flask_login import LoginManager, login_required
from models import User  # Import User model
from emailer.EmailSender import EmailSender
email_sender = EmailSender()

app = Flask(__name__)
app.config.from_object('config.Config')

MAINTANENCE = False

@app.before_request
def is_maintanence():
    if MAINTANENCE:
        return render_template("maintanence.html")
    
    #flash("meow", "info")

# Initialize MongoDB
db_manager = DatabaseManager()
mongo = db_manager.get_db()

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'  # Redirect to login view if not authenticated

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

from organization import organization_bp
app.register_blueprint(organization_bp)

from admin_bp import admin_bp
from admin_user_bp import admin_user_bp
from admin_demo_bp import admin_demo_bp
from admin_org_bp import admin_org_bp
app.register_blueprint(admin_bp)
app.register_blueprint(admin_demo_bp)
app.register_blueprint(admin_user_bp)
app.register_blueprint(admin_org_bp)


from auth import auth_bp

app.register_blueprint(auth_bp, url_prefix="/auth/")

from datetime import datetime

@app.route('/')
def index():
    """
    Display the index page with a list of approved demonstrations.
    """
    search_query = request.args.get('search', '')

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

    # Convert the cursor to a list and sort by date
    demonstrations = list(demonstrations)
    demonstrations.sort(key=lambda x: datetime.strptime(x['date'], "%d.%m.%Y"))

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
    city_query = request.args.get('city', '')
    location_query = request.args.get('location', '')
    date_query = request.args.get('date', '')
    topic_query = request.args.get('topic', '')

    # Build the query dictionary
    query = {"approved": True}

    if search_query:
        query["$or"] = [
            {"title": {"$regex": search_query, "$options": "i"}},
            {"city": {"$regex": search_query, "$options": "i"}},
            {"topic": {"$regex": search_query, "$options": "i"}},
            {"address": {"$regex": search_query, "$options": "i"}}
        ]

    if city_query:
        query["city"] = {"$regex": city_query, "$options": "i"}
    
    if location_query:
        query["address"] = {"$regex": location_query, "$options": "i"}

    if date_query:
        try:
            # Convert the date to a datetime object to ensure it's in the correct format
            parsed_date = datetime.strptime(date_query, "%d.%m.%Y")
            query["date"] = date_query  # Keep the date in string form, since it's stored that way
        except ValueError:
            flash('Invalid date format. Please use pp.kk.vvvv.')

    if topic_query:
        query["topic"] = {"$regex": topic_query, "$options": "i"}

    demonstrations = list(mongo.demonstrations.find(query))

    # Sort the results by date
    demonstrations.sort(key=lambda x: datetime.strptime(x['date'], "%d.%m.%Y"))

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