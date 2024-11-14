import os
import re
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, date
from flask_babel import _, refresh

from flask import (
    render_template,
    redirect,
    url_for,
    request,
    abort,
    Response,
    get_flashed_messages,
    jsonify,
    session
)
from flask_login import current_user

from bson.objectid import ObjectId

from utils.s3 import upload_image
from classes import Organizer, Demonstration, Organization
from database_manager import DatabaseManager
from emailer.EmailSender import EmailSender
from utils.variables import CITY_LIST
from utils.flashing import flash_message
from utils.database import DEMO_FILTER

email_sender = EmailSender()

# Initialize MongoDB
db_manager = DatabaseManager().get_instance()
mongo = db_manager.get_db()
demonstrations_collection = mongo["demonstrations"]


def init_routes(app):
    @app.route("/sitemap.xml", methods=["GET"])
    def sitemap():
        # Create the XML structure
        urlset = ET.Element(
            "urlset", xmlns="http://www.sitemaps.org/schemas/sitemap-image/1.1"
        )

        # List of static routes to include in the sitemap
        routes = [
            {"loc": url_for("index", _external=True)},
            {"loc": url_for("submit", _external=True)},
            {"loc": url_for("demonstrations", _external=True)},
            {"loc": url_for("info", _external=True)},
            {"loc": url_for("privacy", _external=True)},
            {"loc": url_for("contact", _external=True)},
            # Add more static routes as needed
        ]

        # Populate the XML with the static routes
        for route in routes:
            url = ET.SubElement(urlset, "url")
            loc = ET.SubElement(url, "loc")
            loc.text = route["loc"]

        # Fetch all approved demonstrations from the database
        demonstrations = demonstrations_collection.find(DEMO_FILTER)
        for demo in demonstrations:
            url = ET.SubElement(urlset, "url")
            loc = ET.SubElement(url, "loc")
            loc.text = url_for(
                "demonstration_detail", demo_id=demo["_id"], _external=True
            )

        # Convert the XML tree to a string
        xml_str = ET.tostring(urlset, encoding="utf-8", xml_declaration=True)

        return Response(xml_str, mimetype="application/xml")

    @app.route("/")
    def index():
        search_query = request.args.get("search", "")
        today = date.today()  # Use date.today() to get only the date part

        demonstrations = demonstrations_collection.find(DEMO_FILTER)

        filtered_demonstrations = []
        for demo in demonstrations:
            demo_date = datetime.strptime(
                demo["date"], "%d.%m.%Y"
            ).date()  # Convert to date object
            if demo_date >= today:
                if (
                    search_query.lower() in demo["title"].lower()
                    or search_query.lower() in demo["city"].lower()
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
            description = request.form.get("description", "")
            start_time = request.form.get("start_time")
            end_time = request.form.get("end_time", None)
            facebook = request.form.get("facebook")
            city = request.form.get("city")
            address = request.form.get("address")
            event_type = request.form.get("type")
            route = request.form.get("route") if event_type == "marssi" else None
            tags = request.form.get("tags", None)
            tags = [tag.strip() for tag in tags.split(",") if tag.strip()]

            img = request.files.get("image")

            photo_url = ""

            if img:
                # Save the uploaded file temporarily
                temp_file_path = os.path.join("uploads", img.filename)
                img.save(temp_file_path)

                # Define the bucket name and upload the file
                bucket_name = "mielenosoitukset-fi1"  # Your S3 bucket name
                photo_url = upload_image(bucket_name, temp_file_path, "demo_pics")

            # Validation for form data
            if not title or not date or not start_time or not city or not address:
                flash_message("Ole hyvä, ja anna kaikki pakolliset tiedot.", "error")
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
                facebook=facebook,
                city=city,
                address=address,
                event_type=event_type,
                route=route,
                organizers=organizers,
                approved=False,
                img=photo_url,
                description=description,
                tags=tags,
            )

            # Save to MongoDB
            mongo.demonstrations.insert_one(demonstration.to_dict())

            flash_message(
                "Mielenosoitus ilmoitettu onnistuneesti! Tiimimme tarkistaa sen, jonka jälkeen se tulee näkyviin sivustolle.",
                "success",
            )

            return redirect(url_for("index"))

        return render_template("submit.html", city_list=CITY_LIST)

    @app.route("/demonstrations")
    def demonstrations():
        """
        List all upcoming approved demonstrations, optionally filtered by search query.
        """
        # Get pagination parameters
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 10) or 10)
        search_query = request.args.get("search", "").lower()
        city_query = request.args.get("city", "").lower()
        location_query = request.args.get("location", "").lower()
        date_query = request.args.get("date", "")
        today = date.today()

        # Retrieve all approved demonstrations
        demonstrations = demonstrations_collection.find(DEMO_FILTER)

        # Filter upcoming demonstrations
        filtered_demonstrations = filter_demonstrations(
            demonstrations,
            today,
            search_query,
            city_query,
            location_query,
            date_query,
        )

        # Sort the results by date
        filtered_demonstrations.sort(
            key=lambda x: datetime.strptime(x["date"], "%d.%m.%Y").date()
        )

        # Pagination logic
        total_demos = len(filtered_demonstrations)
        total_pages = (total_demos + per_page - 1) // per_page  # Calculate total pages
        start = (page - 1) * per_page
        end = start + per_page

        # Get the items for the current page
        paginated_demonstrations = filtered_demonstrations[start:end]

        return render_template(
            "list.html",
            demonstrations=paginated_demonstrations,
            page=page,
            total_pages=total_pages,
        )

    def filter_demonstrations(
        demonstrations,
        today,
        search_query,
        city_query,
        location_query,
        date_query,
    ):
        """
        Filter the demonstrations based on various criteria.
        """
        filtered = []
        added_demo_ids = set()  # To keep track of added demo IDs

        for demo in demonstrations:
            if is_future_demo(demo, today):
                if (
                    matches_filters(
                        demo,
                        search_query,
                        city_query,
                        location_query,
                        date_query,
                    )
                    and demo["_id"] not in added_demo_ids
                ):
                    filtered.append(demo)
                    added_demo_ids.add(demo["_id"])

        return filtered

    def is_future_demo(demo, today):
        """
        Check if the demonstration is in the future.
        """
        demo_date = datetime.strptime(demo["date"], "%d.%m.%Y").date()
        return demo_date >= today

    def matches_filters(
        demo, search_query, city_query, location_query, date_query  # , topic_query
    ):
        """
        Check if the demonstration matches the filtering criteria.
        """
        matches_search = (
            search_query in demo["title"].lower()
            or search_query in demo["city"].lower()
            or search_query in demo["address"].lower()
        )
        matches_city = city_query in demo["city"].lower() if city_query else True
        matches_location = (
            location_query in demo["address"].lower() if location_query else True
        )
        matches_date = True

        if date_query:
            try:
                parsed_date = datetime.strptime(date_query, "%d.%m.%Y").date()
                matches_date = (
                    parsed_date == datetime.strptime(demo["date"], "%d.%m.%Y").date()
                )
            except ValueError:
                flash_message(
                    _(
                        "Virheellinen päivämäärän muoto. Ole hyvä ja käytä muotoa pp.kk.vvvv."
                    )
                )
                matches_date = False

        return matches_search and matches_city and matches_location and matches_date

    @app.route("/demonstration/<demo_id>")
    def demonstration_detail(demo_id):
        """
        Display details of a specific demonstration and save map coordinates if available.
        """
        # Fetch the demonstration details from MongoDB
        result = demonstrations_collection.find_one({"_id": ObjectId(demo_id)})
        if result:
            demo = Demonstration.from_dict(result)

        else:
            abort(404)

        if not demo:
            flash_message(
                _("Mielenosoitusta ei löytynyt tai sitä ei ole vielä hyväksytty."),
                "error",
            )
            return redirect(url_for("demonstrations"))

        if not demo.approved and not current_user.has_permission("VIEW_DEMO"):
            abort(401)

        # Check if longitude is None to trigger geocoding
        if not demo.longitude:
            # Build the address query (assuming 'address' and 'city' fields in the demo)
            address_query = f"{demo.address}, {demo.city}"

            # Geocode API URL
            api_url = f"https://geocode.maps.co/search?q={address_query}&api_key=66df12ce96495339674278ivnc82595"  # FIXME: Use variable for the api key!

            try:
                # Make the request to the Geocode API
                response = requests.get(api_url)
                response.raise_for_status()
                geocode_data = response.json()

                # Get latitude and longitude from the response
                if geocode_data:
                    latitude = geocode_data[0].get("lat", "None")
                    longitude = geocode_data[0].get("lon", "None")

                    # Save coordinates to the database if they are fetched
                    if latitude and longitude:
                        demo.latitude = latitude
                        demo.longitude = longitude
                        demo.save()

            except (requests.exceptions.RequestException, IndexError):
                ...

        demo = Demonstration.to_dict(demo, True)

        # Pass demo details and coordinates to the template
        return render_template("detail.html", demo=demo)

    @app.route("/info")
    def info():
        return render_template("info.html")

    @app.route("/privacy")
    def privacy():
        return render_template("privacy.html")

    @app.route("/contact", methods=["GET", "POST"])
    def contact():
        if request.method == "POST":
            name = request.form.get("name")
            email = request.form.get("email")
            subject = request.form.get("subject")
            message = request.form.get("message")

            # Validate form data
            if not name or not email or not message:
                flash_message("Kaikki kentät ovat pakollisia!", "error")
                return redirect(url_for("contact"))

            # Create email job
            email_sender.queue_email(
                template_name="customer_support/new_ticket.html",
                subject="Uusi tukipyyntö!",
                recipients=["tuki@mielenosoitukset.fi"],
                context={
                    "name": name,
                    "email": email,
                    "subject": subject,
                    "message": message,
                },
            )

            flash_message("Viesti lähetetty onnistuneesti!", "success")
            return redirect(url_for("contact"))

        return render_template("contact.html")

    @app.route("/organization/<org_id>")
    def org(org_id):
        # Fetch the organization details
        _org = mongo.organizations.find_one({"_id": ObjectId(org_id)})

        if _org is None:
            flash_message("Organisaatiota ei löytynyt.", "error")
            return redirect(url_for("index"))

        _org = Organization.from_dict(_org)

        today = date.today()  # Get today's date

        # Fetch upcoming demonstrations linked to this organization via organizers list
        upcoming_demos_cursor = mongo.demonstrations.find(
            {
                "organizers": {
                    "$elemMatch": {
                        "organization_id": ObjectId(
                            org_id
                        )  # Match the organization_id within the organizers list
                    }
                },
                "approved": True,  # Ensure the demonstration is approved
            }
        )

        # Filter and sort the demonstrations
        upcoming_demos = []
        for demo in upcoming_demos_cursor:
            demo_date = datetime.strptime(
                demo["date"], "%d.%m.%Y"
            ).date()  # Convert date string to date object

            if demo_date >= today:  # Only keep upcoming demos
                upcoming_demos.append(demo)

        # Sort by date
        upcoming_demos.sort(
            key=lambda x: datetime.strptime(x["date"], "%d.%m.%Y").date()
        )

        # Render the organization page with the sorted upcoming demonstrations
        return render_template(
            "organizations/details.html", org=_org, upcoming_demos=upcoming_demos
        )

    @app.route("/tag/<tag_name>")
    def tag_detail(tag_name):
        # Create a case-insensitive regex pattern for the tag
        tag_regex = re.compile(f"^{re.escape(tag_name)}$", re.IGNORECASE)

        # Fetch demonstrations that include the specified tag (case-insensitive)
        demonstrations_query = {"tags": tag_regex, **DEMO_FILTER}

        # Pagination logic
        page = int(request.args.get("page", 1))
        per_page = int(
            request.args.get("per_page", 10) or 10
        )  # Adjust per_page as necessary

        # Get the total number of documents matching the query
        total_demos = mongo.demonstrations.count_documents(demonstrations_query)
        total_pages = (total_demos + per_page - 1) // per_page  # Calculate total pages

        # Fetch the demonstrations cursor
        demonstrations_cursor = mongo.demonstrations.find(demonstrations_query)

        # Get the paginated demonstrations using skip and limit directly on the cursor
        paginated_demos = demonstrations_cursor.skip((page - 1) * per_page).limit(
            per_page
        )

        # Convert paginated_demos to a list to pass to the template
        paginated_demos_list = list(paginated_demos)

        # Render the tag_detail template and pass necessary variables
        return render_template(
            "tag_list.html",
            demonstrations=paginated_demos_list,
            page=page,
            total_pages=total_pages,
            tag_name=tag_name,
        )

    # This is the route that provides the flash_message messages as JSON
    @app.route("/get_flash_messages", methods=["GET"])
    def get_flash_message_messages():
        # Retrieve flash_messageed messages with categories
        messages = get_flashed_messages(with_categories=True)

        # If there are no messages, return an empty array
        if not messages:
            return jsonify(messages=[])

        # Format the flash_message messages into a JSON object
        flash_message_data = [
            {"category": category, "message": message} for category, message in messages
        ]

        # Return the JSON response
        return jsonify(messages=flash_message_data)

    @app.route("/marquee", methods=["GET"])
    def marquee():
        with open("marquee_config.json", "r") as config_file:
            config = json.load(config_file)

        return jsonify(config)

    @app.route("/500")
    def _500():
        return abort(500)
    
    @app.route("/set_language/<lang>")
    def set_language(lang):
        # List of supported languages        
        supported_languages = app.config["BABEL_SUPPORTED_LOCALES"]

        # Validate the language parameter
        if lang not in supported_languages:
            flash_message("Unsupported language selected.", "error")
            return redirect(request.referrer)

        # Set the language cookie
        session["locale"] = lang
        
        session.modified = True
        
        referrer = request.referrer
        if referrer and referrer.startswith(request.host_url):
            return redirect(referrer)
        return redirect(url_for("index"))