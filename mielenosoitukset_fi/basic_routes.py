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
    session,
)
from flask_login import current_user
from bson.objectid import ObjectId
from mielenosoitukset_fi.utils.s3 import upload_image
from mielenosoitukset_fi.utils.classes import Organizer, Demonstration, Organization, RecurringDemonstration
from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.emailer.EmailSender import EmailSender
from mielenosoitukset_fi.utils.variables import CITY_LIST
from mielenosoitukset_fi.utils.flashing import flash_message
from mielenosoitukset_fi.utils.database import DEMO_FILTER
from mielenosoitukset_fi.utils.analytics import log_demo_view
from mielenosoitukset_fi.utils.wrappers import permission_required
from mielenosoitukset_fi.utils.screenshot import trigger_screenshot
from werkzeug.utils import secure_filename
from mielenosoitukset_fi.a import generate_demo_sentence

email_sender = EmailSender()

# Initialize MongoDB
db_manager = DatabaseManager().get_instance()
mongo = db_manager.get_db()
demonstrations_collection = mongo["demonstrations"]


def generate_alternate_urls(app, endpoint, **values):
    """
    Generate alternate URLs for supported languages.
    """
    alternate_urls = {}
    for lang_code in app.config["BABEL_SUPPORTED_LOCALES"]:
        with app.test_request_context():
            alternate_urls[lang_code] = url_for(endpoint, lang_code=lang_code, **values)
    return alternate_urls


def init_routes(app):
    # register genereate_demo_sentence function
    @app.context_processor
    def inject_demo_sentence():
        return dict(generate_demo_sentence=generate_demo_sentence)

    @app.route("/sitemap.xml", methods=["GET"])
    def sitemap():
        try:
            urlset = ET.Element(
                "urlset", {"xmlns:xhtml": "http://www.w3.org/1999/xhtml"}
            )
            routes = [
                {"loc": "index"},
                {"loc": "submit"},
                {"loc": "demonstrations"},
                {"loc": "info"},
                {"loc": "privacy"},
                {"loc": "contact"},
            ]
            for route in routes:
                url = ET.SubElement(urlset, "url")
                loc = ET.SubElement(url, "loc")
                loc.text = url_for(route["loc"], _external=True)
                for alt_lang_code in app.config["BABEL_SUPPORTED_LOCALES"]:
                    ET.SubElement(
                        url,
                        "{http://www.w3.org/1999/xhtml}link",
                        rel="alternate",
                        hreflang=alt_lang_code,
                        href=url_for(
                            route["loc"], lang_code=alt_lang_code, _external=True
                        ),
                    )
            for demo in demonstrations_collection.find():
                demo_url = ET.SubElement(urlset, "url")
                loc = ET.SubElement(demo_url, "loc")
                loc.text = url_for(
                    "demonstration_detail", demo_id=str(demo["_id"]), _external=True
                )
                for alt_lang_code in app.config["BABEL_SUPPORTED_LOCALES"]:
                    ET.SubElement(
                        demo_url,
                        "{http://www.w3.org/1999/xhtml}link",
                        rel="alternate",
                        hreflang=alt_lang_code,
                        href=url_for(
                            "demonstration_detail",
                            demo_id=str(demo["_id"]),
                            lang_code=alt_lang_code,
                            _external=True,
                        ),
                    )
            xml_str = ET.tostring(urlset, encoding="utf-8", xml_declaration=True)
            return Response(xml_str, mimetype="application/xml")
        except Exception as e:
            app.logger.error(f"Error generating sitemap: {e}")
            return Response(status=500)

    @app.context_processor
    def inject_alternate_urls():
        """
        Inject alternate URLs into the template context.
        """
        if request.view_args:
            alternate_urls = generate_alternate_urls(
                app, request.endpoint, **request.view_args
            )
            return dict(alternate_urls=alternate_urls)
        else:
            return dict(alternate_urls={})

    @app.route("/")
    def index():
        search_query = request.args.get("search", "")
        today = date.today()
        demonstrations = demonstrations_collection.find(DEMO_FILTER)
        filtered_demonstrations = []
        for demo in demonstrations:
            demo_date = datetime.strptime(demo["date"], "%d.%m.%Y").date()
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
                filename = secure_filename(img.filename)
                temp_file_path = os.path.join("mielenosoitukset_fi/uploads", filename)
                img.save(temp_file_path)
                bucket_name = "mielenosoitukset-fi1"
                photo_url = upload_image(bucket_name, temp_file_path, "demo_pics")
            if not title or not date or not start_time or not city or not address:
                flash_message("Ole hyvä, ja anna kaikki pakolliset tiedot.", "error")
                return redirect(url_for("submit"))
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
            mongo.demonstrations.insert_one(demonstration.to_dict())
            flash_message(
                "Mielenosoitus ilmoitettu onnistuneesti! Tiimimme tarkistaa sen, jonka jälkeen se tulee näkyviin sivustolle.",
                "success",
            )
            return redirect(url_for("index"))
        return render_template("submit.html", city_list=CITY_LIST)

    @app.route("/report", methods=["GET", "POST"])
    def report():
        """
        Handle submission of a new demonstration.
        """
        error = request.form.get("error")
        _type = request.form.get("type")
        if _type:
            if _type == "demonstration":
                mongo.reports.insert_one(
                    {
                        "error": error,
                        "demo_id": ObjectId(request.form.get("demo_id")),
                        "date": datetime.now(),
                        "user": (
                            ObjectId(current_user._id)
                            if current_user.is_authenticated
                            else None
                        ),
                        "ip": request.remote_addr,
                    }
                )

        else:
            mongo.reports.insert_one(
                {
                    "error": error,
                    "date": datetime.now(),
                    "user": current_user._id if current_user.is_authenticated else None,
                    "ip": request.remote_addr,
                }
            )

        flash_message(
            "Virhe ilmoitettu onnistuneesti! Kiitos ilmoituksestasi.", "success"
        )
        return redirect(request.referrer)

    @app.route("/demonstrations")
    def demonstrations():
        """
        List all upcoming approved demonstrations, optionally filtered by search query.
        """
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 10) or 10)
        search_query = request.args.get("search", "").lower()

        # if city contains , then it is a list of cities
        city_query = request.args.get("city", "").lower()

        if "," in city_query:
            city_query = city_query.split(",")

        location_query = request.args.get("location", "").lower()
        date_query = request.args.get("date", "")
        today = date.today()
        demonstrations = demonstrations_collection.find(DEMO_FILTER)
        filtered_demonstrations = filter_demonstrations(
            demonstrations, today, search_query, city_query, location_query, date_query
        )
        filtered_demonstrations.sort(
            key=lambda x: datetime.strptime(x["date"], "%d.%m.%Y").date()
        )
        total_demos = len(filtered_demonstrations)
        total_pages = (total_demos + per_page - 1) // per_page
        start = (page - 1) * per_page
        end = start + per_page
        paginated_demonstrations = filtered_demonstrations[start:end]
        return render_template(
            "list.html",
            demonstrations=paginated_demonstrations,
            page=page,
            total_pages=total_pages,
            city_list=CITY_LIST,
        )

    @app.route("/city/<city>")
    def city_demos(city):
        """
        List all upcoming approved demonstrations, optionally filtered by search query.
        """
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 10) or 10)
        search_query = request.args.get("search", "").lower()
        city_query = city
        location_query = request.args.get("location", "").lower()
        date_query = request.args.get("date", "")
        today = date.today()
        demonstrations = demonstrations_collection.find(DEMO_FILTER)
        filtered_demonstrations = filter_demonstrations(
            demonstrations, today, search_query, city_query, location_query, date_query
        )
        filtered_demonstrations.sort(
            key=lambda x: datetime.strptime(x["date"], "%d.%m.%Y").date()
        )
        total_demos = len(filtered_demonstrations)
        total_pages = (total_demos + per_page - 1) // per_page
        start = (page - 1) * per_page
        end = start + per_page
        paginated_demonstrations = filtered_demonstrations[start:end]
        return render_template(
            "city.html",
            demonstrations=paginated_demonstrations,
            page=page,
            total_pages=total_pages,
            city_name=city.capitalize(),
        )

    def filter_demonstrations(
        demonstrations, today, search_query, city_query, location_query, date_query
    ):
        """
        Filter the demonstrations based on various criteria.
        """
        filtered = []
        added_demo_ids = set()
        for demo in demonstrations:
            if is_future_demo(demo, today):
                if (
                    matches_filters(
                        demo, search_query, city_query, location_query, date_query
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

    def matches_filters(demo, search_query, city_query, location_query, date_query):
        """
        Check if the demonstration matches the filtering criteria.
        """
        matches_search = (
            search_query in demo["title"].lower()
            or search_query in demo["address"].lower()
        )
        matches_city = (
            any(city in demo["city"].lower() for city in city_query)
            if isinstance(city_query, list)
            else city_query in demo["city"].lower()
        )
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
        if not demo.longitude:
            address_query = f"{demo.address}, {demo.city}"
            api_url = f"https://geocode.maps.co/search?q={address_query}&api_key=66df12ce96495339674278ivnc82595"
            try:
                response = requests.get(api_url)
                response.raise_for_status()
                geocode_data = response.json()
                if geocode_data:
                    latitude = geocode_data[0].get("lat", "None")
                    longitude = geocode_data[0].get("lon", "None")
                    if latitude and longitude:
                        demo.latitude = latitude
                        demo.longitude = longitude
                        demo.save()
            except (requests.exceptions.RequestException, IndexError):
                ...
        demo = Demonstration.to_dict(demo, True)
        log_demo_view(
            demo_id, current_user._id if current_user.is_authenticated else None
        )
        trigger_screenshot(demo_id)
        return render_template("detail.html", demo=demo)

    @app.route("/demonstration/<demo_id>/some", methods=["GET"])
    @permission_required("VIEW_DEMO")
    def preview(demo_id):
        """
        Display details of a specific demonstration and save map coordinates if available.
        """
        result = demonstrations_collection.find_one(
            {
                "$or": [
                    {"_id": ObjectId(demo_id)},
                    {"aliases": {"$in": [ObjectId(demo_id)]}},
                ]
            }
        )
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
        if not demo.longitude:
            address_query = f"{demo.address}, {demo.city}"
            api_url = f"https://geocode.maps.co/search?q={address_query}&api_key=66df12ce96495339674278ivnc82595"
            try:
                response = requests.get(api_url)
                response.raise_for_status()
                geocode_data = response.json()
                if geocode_data:
                    latitude = geocode_data[0].get("lat", "None")
                    longitude = geocode_data[0].get("lon", "None")
                    if latitude and longitude:
                        demo.latitude = latitude
                        demo.longitude = longitude
                        demo.save()
            except (requests.exceptions.RequestException, IndexError):
                ...
        demo = Demonstration.to_dict(demo, True)
        log_demo_view(
            demo_id, current_user._id if current_user.is_authenticated else None
        )
        return render_template("preview.html", demo=demo)

    @app.route("/demonstration/<parent>/children", methods=["GET"])
    def siblings_meeting(parent):
        result = demonstrations_collection.find(
            {"parent": ObjectId(parent), "hide": False}
        )
        
        # also get the parent from repeated demonstrations
        parent_demo = RecurringDemonstration.from_id(parent)

        """
        List all sibling demonstrations of a recurring demonstration.
        """
        siblings = []
        for demo in result:
            siblings.append(Demonstration.from_dict(demo))
        siblings.sort(key=lambda x: datetime.strptime(x.date, "%d.%m.%Y").date())
        return render_template("siblings.html", siblings=siblings, parent_demo=parent_demo)

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
            if not name or not email or not message:
                flash_message("Kaikki kentät ovat pakollisia!", "error")
                return redirect(url_for("contact"))
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
        _org = mongo.organizations.find_one({"_id": ObjectId(org_id)})
        if _org is None:
            flash_message("Organisaatiota ei löytynyt.", "error")
            return redirect(url_for("index"))
        _org = Organization.from_dict(_org)
        today = date.today()
        upcoming_demos_cursor = mongo.demonstrations.find(
            {
                "organizers": {"$elemMatch": {"organization_id": ObjectId(org_id)}},
                "approved": True,
            }
        )
        upcoming_demos = []
        for demo in upcoming_demos_cursor:
            demo_date = datetime.strptime(demo["date"], "%d.%m.%Y").date()
            if demo_date >= today:
                upcoming_demos.append(demo)
        upcoming_demos.sort(
            key=lambda x: datetime.strptime(x["date"], "%d.%m.%Y").date()
        )
        return render_template(
            "organizations/details.html", org=_org, upcoming_demos=upcoming_demos
        )

    @app.route("/tag/<tag_name>")
    def tag_detail(tag_name):
        tag_regex = re.compile(f"^{re.escape(tag_name)}$", re.IGNORECASE)
        demonstrations_query = {"tags": tag_regex, **DEMO_FILTER}
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 10) or 10)
        total_demos = mongo.demonstrations.count_documents(demonstrations_query)
        total_pages = (total_demos + per_page - 1) // per_page
        demonstrations_cursor = mongo.demonstrations.find(demonstrations_query)
        paginated_demos = demonstrations_cursor.skip((page - 1) * per_page).limit(
            per_page
        )
        paginated_demos_list = list(paginated_demos)
        return render_template(
            "tag_list.html",
            demonstrations=paginated_demos_list,
            page=page,
            total_pages=total_pages,
            tag_name=tag_name,
        )

    @app.route("/get_flash_messages", methods=["GET"])
    def get_flash_message_messages():
        messages = get_flashed_messages(with_categories=True)
        if not messages:
            return jsonify(messages=[])
        flash_message_data = [
            {"category": category, "message": message} for category, message in messages
        ]
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
        supported_languages = app.config["BABEL_SUPPORTED_LOCALES"]
        if lang not in supported_languages:
            flash_message("Unsupported language selected.", "error")
            return redirect(request.referrer)
        session["locale"] = lang
        session.modified = True
        referrer = request.referrer
        if referrer and referrer.startswith(request.host_url):
            return redirect(referrer)
        return redirect(url_for("index"))

    @app.before_request
    def preprocess_url():
        supported_languages = app.config["BABEL_SUPPORTED_LOCALES"]
        path = request.path.strip("/").split("/")
        if path and path[0] in supported_languages:
            lang = path[0]
            session["locale"] = lang
            session.modified = True
            new_path = "/" + "/".join(path[1:])
            return redirect(new_path)
