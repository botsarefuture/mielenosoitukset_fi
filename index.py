from flask import Flask, render_template, request, redirect, url_for, flash
from bson.objectid import ObjectId
from classes import Organizer, Demonstration
from database_manager import DatabaseManager
from flask_login import LoginManager, login_required
from models import User  # Import User model
from wrappers import admin_required
from datetime import datetime
from emailer.EmailSender import EmailSender
email_sender = EmailSender()

app = Flask(__name__)
app.config.from_object('config.Config')

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

from organization import organization_bp # TODO: Remove this
app.register_blueprint(organization_bp) # TODO: Remove this

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


@app.route('/')
def index():
    """
    Display the index page with a list of upcoming approved demonstrations.
    """
    search_query = request.args.get('search', '')
    today = datetime.now()

    # Retrieve all approved demonstrations
    demonstrations = mongo.demonstrations.find({"approved": True})

    # Filter out past demonstrations manually
    filtered_demonstrations = []
    for demo in demonstrations:
        demo_date = datetime.strptime(demo['date'], "%d.%m.%Y")
        if demo_date >= today:
            # Check for search query match
            if (search_query.lower() in demo['title'].lower() or
                search_query.lower() in demo['city'].lower() or
                search_query.lower() in demo['topic'].lower() or
                search_query.lower() in demo['address'].lower()):
                filtered_demonstrations.append(demo)

    # Sort the results by date
    filtered_demonstrations.sort(key=lambda x: datetime.strptime(x['date'], "%d.%m.%Y"))

    return render_template('index.html', demonstrations=filtered_demonstrations)

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
            flash('Sinun tulee antaa kaikki vaaditut tiedot.', 'error')
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

        flash('Mielenosoitus ilmoitettu onnistuneesti! Tiimimme tarkistaa sen, jonka jälkeen se tulee näkyviin sivustolle.')
        return redirect(url_for('index'))

    return render_template('submit.html')
@app.route('/demonstrations')
def demonstrations():
    """
    List all upcoming approved demonstrations, optionally filtered by search query.
    """
    search_query = request.args.get('search', '')
    city_query = request.args.get('city', '')
    location_query = request.args.get('location', '')
    date_query = request.args.get('date', '')
    topic_query = request.args.get('topic', '')
    today = datetime.now()

    # Retrieve all approved demonstrations
    demonstrations = mongo.demonstrations.find({"approved": True})

    # Filter out past demonstrations manually
    filtered_demonstrations = []
    for demo in demonstrations:
        demo_date = datetime.strptime(demo['date'], "%d.%m.%Y")
        if demo_date >= today:
            # Apply additional filters
            if (search_query.lower() in demo['title'].lower() or
                search_query.lower() in demo['city'].lower() or
                search_query.lower() in demo['topic'].lower() or
                search_query.lower() in demo['address'].lower()):
                
                if city_query.lower() in demo['city'].lower():
                    if location_query.lower() in demo['address'].lower():
                        if date_query:
                            try:
                                parsed_date = datetime.strptime(date_query, "%d.%m.%Y")
                                if parsed_date.strftime("%d.%m.%Y") == demo['date']:
                                    filtered_demonstrations.append(demo)
                            except ValueError:
                                flash('Virheellinen päivämäärän muoto. Ole hyvä ja käytä muotoa pp.kk.vvvv.')
                        else:
                            filtered_demonstrations.append(demo)

                if topic_query.lower() in demo['topic'].lower():
                    filtered_demonstrations.append(demo)

    # Sort the results by date
    filtered_demonstrations.sort(key=lambda x: datetime.strptime(x['date'], "%d.%m.%Y"))

    return render_template('list.html', demonstrations=filtered_demonstrations)

@app.route('/demonstration/<demo_id>')
def demonstration_detail(demo_id):
    """
    Display details of a specific demonstration.
    """
    demo = mongo.demonstrations.find_one({"_id": ObjectId(demo_id), "approved": True})

    if demo is None:
        flash("Mielenosoitusta ei löytynyt tai sitä ei ole vielä hyväksytty.")
        return redirect(url_for('demonstrations'))

    return render_template('detail.html', demo=demo)

if __name__ == '__main__':
    app.run(debug=True)