from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_pymongo import PyMongo
from flask_mail import Mail, Message
from bson.objectid import ObjectId

app = Flask(__name__)
app.config.from_object('config.Config')

# Initialize MongoDB and Mail
mongo = PyMongo(app)
mail = Mail(app)

# Home route
@app.route('/')
def index():
    search_query = request.args.get('search', '')

    if search_query:
        demonstrations = mongo.db.demonstrations.find({
            "approved": True,
            "$or": [
                {"title": {"$regex": search_query, "$options": "i"}},
                {"city": {"$regex": search_query, "$options": "i"}},
                {"topic": {"$regex": search_query, "$options": "i"}},
                {"address": {"$regex": search_query, "$options": "i"}}
            ]
        })
    else:
        demonstrations = mongo.db.demonstrations.find({"approved": True})

    return render_template('index.html', demonstrations=demonstrations)

@app.route('/submit', methods=['GET', 'POST'])
def submit():
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
        route = request.form.get('route')

        # Get organizers
        organizers = []
        i = 1
        while f'organizer_name_{i}' in request.form:
            organizer = {
                'name': request.form.get(f'organizer_name_{i}'),
                'website': request.form.get(f'organizer_website_{i}'),
                'email': request.form.get(f'organizer_email_{i}')
            }
            organizers.append(organizer)
            i += 1

        # Save to MongoDB
        mongo.db.demonstrations.insert_one({
            'title': title,
            'date': date,
            'start_time': start_time,
            'end_time': end_time,
            'topic': topic,
            'facebook': facebook,
            'city': city,
            'address': address,
            'type': event_type,
            'route': route,
            'organizers': organizers,
            'approved': False
        })

        flash('Demonstration submitted successfully! It will be reviewed by an admin.')
        return redirect(url_for('index'))

    return render_template('submit.html')


@app.route('/demonstrations')
def demonstrations():
    search_query = request.args.get('search', '')

    if search_query:
        demonstrations = mongo.db.demonstrations.find({
            "approved": True,
            "$or": [
                {"title": {"$regex": search_query, "$options": "i"}},
                {"location": {"$regex": search_query, "$options": "i"}},
                {"organizer": {"$regex": search_query, "$options": "i"}}
            ]
        })
    else:
        demonstrations = mongo.db.demonstrations.find({"approved": True})

    return render_template('list.html', demonstrations=demonstrations)

@app.route('/demonstration/<demo_id>')
def demonstration_detail(demo_id):
    demo = mongo.db.demonstrations.find_one({"_id": ObjectId(demo_id), "approved": True})

    if demo is None:
        flash("Demonstration not found or not approved.")
        return redirect(url_for('demonstrations'))

    return render_template('detail.html', demo=demo)


@app.route('/edit/<demo_id>', methods=['GET', 'POST'])
def edit_event(demo_id):
    if not session.get('admin'):
        flash("You are not authorized to access this page.")
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        # Get form data
        title = request.form.get('title')
        topic = request.form.get('topic')
        event_type = request.form.get('type')
        organizer = request.form.get('organizer')
        route = request.form.get('route') if event_type == 'marssi' else None
        facebook = request.form.get('facebook')
        email = request.form.get('email')

        # Update event data in MongoDB
        mongo.db.demonstrations.update_one(
            {"_id": ObjectId(demo_id)},
            {
                "$set": {
                    'title': title,
                    'topic': topic,
                    'type': event_type,
                    'organizer': organizer,
                    'route': route,
                    'facebook': facebook,
                    'email': email
                }
            }
        )
        flash('Event updated successfully!')
        return redirect(url_for('demonstration_detail', demo_id=demo_id))

    # GET request - fetch event details
    demo = mongo.db.demonstrations.find_one({"_id": ObjectId(demo_id)})
    if demo is None:
        flash("Event not found.")
        return redirect(url_for('demonstrations'))

    return render_template('edit_event.html', demo=demo)

@app.route('/delete/<demo_id>', methods=['POST'])
def delete_event(demo_id):
    if not session.get('admin'):
        flash("You are not authorized to delete this event.")
        return redirect(url_for('demonstrations'))

    demo = mongo.db.demonstrations.find_one({"_id": ObjectId(demo_id)})

    if demo is None:
        flash("Event not found.")
        return redirect(url_for('demonstrations'))

    mongo.db.demonstrations.delete_one({"_id": ObjectId(demo_id)})
    flash('Event deleted successfully!')
    return redirect(url_for('demonstrations'))


# ADMIN ROUTES

# Admin login route
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Basic hardcoded admin credentials (you should use a more secure method)
        if username == 'admin' and password == 'password':
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))

        flash('Invalid credentials')

    return render_template('admin_login.html')

# Admin dashboard
@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    pending_demos = mongo.db.demonstrations.find({"approved": False})
    return render_template('admin_dashboard.html', pending_demos=pending_demos)

# Admin logout route
@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login'))

@app.route('/admin/approve/<demo_id>')
def approve_demo(demo_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    mongo.db.demonstrations.update_one(
        {"_id": ObjectId(demo_id)},
        {"$set": {"approved": True}}
    )
    flash('Demonstration approved.')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reject/<demo_id>')
def reject_demo(demo_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    mongo.db.demonstrations.delete_one({"_id": ObjectId(demo_id)})
    flash('Demonstration rejected.')
    return redirect(url_for('admin_dashboard'))


if __name__ == '__main__':
    app.run(debug=True)
