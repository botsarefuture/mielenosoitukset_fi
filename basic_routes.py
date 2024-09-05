from flask import render_template, request, redirect, url_for, flash
from bson.objectid import ObjectId
from datetime import datetime
from classes import Organizer, Demonstration
from database_manager import DatabaseManager
from flask_login import current_user
from datetime import date

from emailer.EmailSender import EmailSender, EmailJob

email_sender = EmailSender()

# Initialize MongoDB
db_manager = DatabaseManager()
mongo = db_manager.get_db()


def init_routes(app):
    @app.route("/")
    def index():
        search_query = request.args.get("search", "")
        today = date.today()  # Use date.today() to get only the date part

        demonstrations = mongo.demonstrations.find({"approved": True})

        filtered_demonstrations = []
        for demo in demonstrations:
            demo_date = datetime.strptime(
                demo["date"], "%d.%m.%Y"
            ).date()  # Convert to date object
            if demo_date >= today:
                if (
                    search_query.lower() in demo["title"].lower()
                    or search_query.lower() in demo["city"].lower()
                    or search_query.lower() in demo["topic"].lower()
                    or search_query.lower() in demo["address"].lower()
                ):
                    filtered_demonstrations.append(demo)

        filtered_demonstrations.sort(
            key=lambda x: datetime.strptime(x["date"], "%d.%m.%Y").date()
        )

        return render_template("index.html", demonstrations=filtered_demonstrations)

    @app.route("/submit", methods=["GET", "POST"])
    def submit():
        """
        Handle submission of a new demonstration.
        """
        if request.method == "POST":
            # Get form data
            title = request.form.get("title")
            date = request.form.get("date")
            start_time = request.form.get("start_time")
            end_time = request.form.get("end_time", None)
            topic = request.form.get("topic")
            facebook = request.form.get("facebook")
            city = request.form.get("city")
            address = request.form.get("address")
            event_type = request.form.get("type")
            route = request.form.get("route") if event_type == "marssi" else None

            # Validation for form data
            if (
                not title
                or not date
                or not start_time
                or not topic
                or not city
                or not address
            ):
                flash("Sinun tulee antaa kaikki vaaditut tiedot.", "error")
                return redirect(url_for("submit"))

            # Get organizers from the form and create Organizer instances
            organizers = []
            i = 1
            while f"organizer_name_{i}" in request.form:
                organizer = Organizer(
                    name=request.form.get(f"organizer_name_{i}"),
                    email=request.form.get(f"organizer_email_{i}"),
                    website=request.form.get(f"organizer_website_{i}"),
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
                approved=False,
            )

            # Save to MongoDB
            mongo.demonstrations.insert_one(demonstration.to_dict())

            flash(
                "Mielenosoitus ilmoitettu onnistuneesti! Tiimimme tarkistaa sen, jonka jälkeen se tulee näkyviin sivustolle.",
                "success",
            )
            return redirect(url_for("index"))

        return render_template("submit.html")

    @app.route("/demonstrations")
    def demonstrations():
        """
        List all upcoming approved demonstrations, optionally filtered by search query.
        """
        search_query = request.args.get("search", "")
        city_query = request.args.get("city", "")
        location_query = request.args.get("location", "")
        date_query = request.args.get("date", "")
        topic_query = request.args.get("topic", "")
        today = date.today()  # Use date.today() to get only the date part

        # Retrieve all approved demonstrations
        demonstrations = mongo.demonstrations.find({"approved": True})

        # Filter out past demonstrations manually
        filtered_demonstrations = []
        added_demo_ids = set()  # To keep track of added demo IDs

        for demo in demonstrations:
            demo_date = datetime.strptime(
                demo["date"], "%d.%m.%Y"
            ).date()  # Convert to date object
            if demo_date >= today:
                # Apply additional filters
                matches_search = (
                    search_query.lower() in demo["title"].lower()
                    or search_query.lower() in demo["city"].lower()
                    or search_query.lower() in demo["topic"].lower()
                    or search_query.lower() in demo["address"].lower()
                )

                matches_city = (
                    city_query.lower() in demo["city"].lower() if city_query else True
                )
                matches_location = (
                    location_query.lower() in demo["address"].lower()
                    if location_query
                    else True
                )
                matches_topic = (
                    topic_query.lower() in demo["topic"].lower()
                    if topic_query
                    else True
                )

                matches_date = True
                if date_query:
                    try:
                        parsed_date = datetime.strptime(
                            date_query, "%d.%m.%Y"
                        ).date()  # Convert to date object
                        matches_date = parsed_date == demo_date
                    except ValueError:
                        flash(
                            "Virheellinen päivämäärän muoto. Ole hyvä ja käytä muotoa pp.kk.vvvv."
                        )
                        matches_date = False

                if (
                    matches_search
                    and matches_city
                    and matches_location
                    and matches_topic
                    and matches_date
                ):
                    if (
                        demo["_id"] not in added_demo_ids
                    ):  # Ensure the demo isn't already added
                        filtered_demonstrations.append(demo)
                        added_demo_ids.add(demo["_id"])  # Mark the demo as added

        # Sort the results by date
        filtered_demonstrations.sort(
            key=lambda x: datetime.strptime(x["date"], "%d.%m.%Y").date()
        )

        return render_template("list.html", demonstrations=filtered_demonstrations)

    @app.route("/demonstration/<demo_id>")
    def demonstration_detail(demo_id):
        """
        Display details of a specific demonstration.
        """
        demo = mongo.demonstrations.find_one(
            {"_id": ObjectId(demo_id), "approved": True}
        )

        if demo is None:
            flash("Mielenosoitusta ei löytynyt tai sitä ei ole vielä hyväksytty.")
            return redirect(url_for("demonstrations"))

        return render_template("detail.html", demo=demo)

    @app.route("/info")
    def info():
        return render_template("info.html")

    @app.route("/privacy")
    def privacy():
        return render_template("access_denied.html")

    @app.route("/contact", methods=["GET", "POST"])
    def contact():
        if request.method == "POST":
            name = request.form.get("name")
            email = request.form.get("email")
            subject = request.form.get("subject")
            message = request.form.get("message")

            # Validate form data
            if not name or not email or not message:
                flash("Kaikki kentät ovat pakollisia!", "error")
                return redirect(url_for("contact"))

            # Create email job
            email_sender.queue_email(
                template_name="new_ticket.html",
                subject="Uusi viesti Mielenosoitukset.fi:stä",
                recipients=["tuki@mielenosoitukset.fi"],
                context={
                    "name": name,
                    "email": email,
                    "subject": subject,
                    "message": message,
                },
            )

            flash("Viesti lähetetty onnistuneesti!", "success")
            return redirect(url_for("contact"))

        return render_template("contact.html")
