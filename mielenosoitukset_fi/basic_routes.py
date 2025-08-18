import copy
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
    send_file,
    send_from_directory,
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
from mielenosoitukset_fi.utils.s3 import upload_image_fileobj
from mielenosoitukset_fi.utils.classes import Organizer, Demonstration, Organization, RecurringDemonstration
from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.emailer.EmailSender import EmailSender
from mielenosoitukset_fi.utils.variables import CITY_LIST
from mielenosoitukset_fi.utils.flashing import flash_message
from mielenosoitukset_fi.utils.database import DEMO_FILTER
from mielenosoitukset_fi.utils.analytics import log_demo_view
from mielenosoitukset_fi.utils.wrappers import permission_required, depracated_endpoint
from mielenosoitukset_fi.utils.screenshot import trigger_screenshot
from werkzeug.utils import secure_filename
from mielenosoitukset_fi.a import generate_demo_sentence
from flask_caching import Cache  # New import for caching

email_sender = EmailSender()

# Initialize MongoDB
db_manager = DatabaseManager().get_instance()
mongo = db_manager.get_db()
demonstrations_collection = mongo["demonstrations"]
submitters_collection = mongo["submitters"]  # <-- Add this line


def generate_alternate_urls(app, endpoint, **values):
    """
    Generate alternate URLs for supported languages.
    """
    alternate_urls = {}
    for lang_code in app.config["BABEL_SUPPORTED_LOCALES"]:
        with app.test_request_context():
            alternate_urls[lang_code] = url_for(endpoint, lang_code=lang_code, **values)
    return alternate_urls

def format_demo_for_api(demo):
    """
    Format a demonstration document for API output.

    Parameters
    ----------
    demo : dict
        The demonstration document from MongoDB.

    Returns
    -------
    dict
        Dictionary with only the fields needed for API rendering.
    """
    def fmt_time(t):
        """
        Format time string to HH:MM.

        Parameters
        ----------
        t : str

        Returns
        -------
        str
        """
        if not t:
            return ""
        try:
            try:
                return datetime.strptime(t, "%H:%M:%S").strftime("%H:%M")
            except ValueError:
                return datetime.strptime(t, "%H:%M").strftime("%H:%M")
        except Exception:
            print(t)
            return t

    try:
        date_obj = datetime.strptime(demo.get("date", ""), "%Y-%m-%d")
        date_display = date_obj.strftime("%d.%m.%Y")
    except Exception:
        date_display = demo.get("date", "")

    return {
        "_id": str(demo.get("_id")),
        "title": demo.get("title", ""),
        "date_display": date_display,
        "start_time_display": fmt_time(demo.get("start_time")),
        "end_time_display": fmt_time(demo.get("end_time")),
        "city": demo.get("city", ""),
        "address": demo.get("address", ""),
        "tags": demo.get("tags", []),
        "topic": demo.get("topic", ""),
    }


def filter_demonstrations_api(
    demonstrations, today, search_query, city_query, location_query, date_start, date_end, tag_query=None
):
    """
    Filter the demonstrations for the API based on various criteria.

    Parameters
    ----------
    demonstrations : iterable
        Demonstration documents.
    today : date
        Today's date.
    search_query : str
        Search term.
    city_query : str or list
        City/cities.
    location_query : str
        Location.
    date_start : str
        Start date (YYYY-MM-DD).
    date_end : str
        End date (YYYY-MM-DD).
    tag_query : str or None
        Tag to filter by.

    Returns
    -------
    list
        Filtered demonstration dicts.
    """
    filtered = []
    added_demo_ids = set()
    for demo in demonstrations:
        # Only approved and not hidden
        if not demo.get("approved", True) or demo.get("hide", False):
            continue
        try:
            demo_date = datetime.strptime(demo["date"], "%Y-%m-%d").date()
        except Exception:
            continue
        if demo_date < today:
            continue
        # Search
        if search_query:
            if search_query not in demo.get("title", "").lower() and \
               search_query not in demo.get("address", "").lower():
                continue
        # City
        if city_query:
            if isinstance(city_query, list):
                if not any(city in demo.get("city", "").lower() for city in city_query):
                    continue
            else:
                if city_query not in demo.get("city", "").lower():
                    continue
        # Location
        if location_query:
            if location_query not in demo.get("address", "").lower():
                continue
        # Date range
        if date_start and date_end:
            try:
                start_date = datetime.strptime(date_start, "%Y-%m-%d").date()
                end_date = datetime.strptime(date_end, "%Y-%m-%d").date()
                if not (start_date <= demo_date <= end_date):
                    continue
            except Exception:
                pass
        # Tag filter
        if tag_query:
            tags = [t.lower() for t in demo.get("tags", [])]
            if tag_query.lower() not in tags:
                continue
        if demo["_id"] not in added_demo_ids:
            filtered.append(demo)
            added_demo_ids.add(demo["_id"])
    return filtered


def parse_city_query(city_query):
    """
    Parse the city query string into a list if needed.

    Parameters
    ----------
    city_query : str

    Returns
    -------
    str or list
    """
    if "," in city_query:
        return [c.strip().lower() for c in city_query.split(",") if c.strip()]
    return city_query.lower() if city_query else ""


def parse_date_arg(arg):
    """
    Parse a date argument from request args.

    Parameters
    ----------
    arg : str

    Returns
    -------
    str or None
    """
    if arg and re.match(r"\d{4}-\d{2}-\d{2}", arg):
        return arg
    return None


def get_api_pagination_args():
    """
    Get pagination and filter arguments from request.args.

    Returns
    -------
    dict
        Contains page, per_page, search, city, location, date_start, date_end, tag.
    """
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20) or 20)
    search_query = request.args.get("search", "").lower()
    city_query = parse_city_query(request.args.get("city", ""))
    location_query = request.args.get("location", "").lower()
    date_start = parse_date_arg(request.args.get("date_start", ""))
    date_end = parse_date_arg(request.args.get("date_end", ""))
    tag_query = request.args.get("tag", "").strip().lower() or None
    return dict(
        page=page,
        per_page=per_page,
        search_query=search_query,
        city_query=city_query,
        location_query=location_query,
        date_start=date_start,
        date_end=date_end,
        tag_query=tag_query,
    )


def paginate_list(items, page, per_page):
    """
    Paginate a list.

    Parameters
    ----------
    items : list
    page : int
    per_page : int

    Returns
    -------
    tuple
        (paginated_items, total_pages)
    """
    total = len(items)
    total_pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    return items[start:end], total_pages


def add_api_routes(app):
    """
    Register API routes for demonstrations.

    Parameters
    ----------
    app : Flask
    """
    @app.route("/api/v1/demonstrations", methods=["GET"])
    def api_demonstrations():
        """
        API endpoint for demonstration list.

        Returns
        -------
        response : flask.Response
            JSON with keys: demonstrations, total_pages
        """
        args = get_api_pagination_args()
        today = date.today()
        demos_cursor = demonstrations_collection.find(DEMO_FILTER)
        filtered = filter_demonstrations_api(
            demos_cursor,
            today,
            args["search_query"],
            args["city_query"],
            args["location_query"],
            args["date_start"],
            args["date_end"],
            args.get("tag_query"),
        )
        filtered.sort(key=lambda x: datetime.strptime(x["date"], "%Y-%m-%d").date())
        paginated, total_pages = paginate_list(filtered, args["page"], args["per_page"])
        result = [format_demo_for_api(demo) for demo in paginated]
        return jsonify(demonstrations=result, total_pages=total_pages)


def init_routes(app):
    # Retrieve the cache instance from app extensions
    cache = app.extensions.get("cache")
    
    # register genereate_demo_sentence function
    @app.context_processor
    def inject_demo_sentence():
        return dict(generate_demo_sentence=generate_demo_sentence)

    @app.route("/robots.txt")
    def robottext():
        return '''User-agent: *\n
Disallow: /admin/
'''
        
    from flask import Response, url_for
    import xml.etree.ElementTree as ET
    from flask import Flask, Response, url_for
    import xml.etree.ElementTree as ET


    @app.route("/sitemap.xml", methods=["GET"])
    def sitemap():
        try:
            # Define the sitemap root element with both the sitemap and XHTML namespaces
            urlset = ET.Element("urlset", {
                "xmlns": "http://www.google.com/schemas/sitemap/0.84",
                "xmlns:xhtml": "http://www.w3.org/1999/xhtml"
            })
            
            # List of static routes
            routes = [
                {"loc": "index"},
                {"loc": "submit"},
                {"loc": "demonstrations"},
                {"loc": "info"},
                {"loc": "privacy"},
                {"loc": "contact"},
            ]
            
            # Add static URLs to the sitemap
            for route in routes:
                url = ET.SubElement(urlset, "url")
                loc = ET.SubElement(url, "loc")
                loc.text = url_for(route["loc"], _external=True)
                
                # Add alternate language versions
                for alt_lang_code in app.config["BABEL_SUPPORTED_LOCALES"]:
                    ET.SubElement(
                        url,
                        "{http://www.w3.org/1999/xhtml}link",
                        rel="alternate",
                        hreflang=alt_lang_code,
                        href=url_for(route["loc"], lang_code=alt_lang_code, _external=True)
                    )
            
            # Add demonstration URLs to the sitemap
            for demo in demonstrations_collection.find(DEMO_FILTER):
                demo_url = ET.SubElement(urlset, "url")
                demo_id = demo.get("slug") or demo.get("running_number") or str(demo["_id"])
                loc = ET.SubElement(demo_url, "loc")
                loc.text = url_for("demonstration_detail", demo_id=demo_id, _external=True)
                # Add alternate language versions for each demonstration
                for alt_lang_code in app.config["BABEL_SUPPORTED_LOCALES"]:
                    ET.SubElement(
                        demo_url,
                        "{http://www.w3.org/1999/xhtml}link",
                        rel="alternate",
                        hreflang=alt_lang_code,
                        href=url_for("demonstration_detail", demo_id=demo_id, lang_code=alt_lang_code, _external=True)
                    )
            
            # Convert the tree to a string and send as response
            xml_str = ET.tostring(urlset, encoding="utf-8", xml_declaration=True)
            return Response(xml_str, mimetype="text/xml", content_type='text/xml')
        
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
        
    # inject city list to the template context
    @app.context_processor
    def inject_city_list():
        """
        Inject the city list into the template context.
        """
        return dict(city_list=CITY_LIST)
    

    @app.route("/")
    def index():
        """
        Render the index page with recommended and featured demonstrations.
        Uses caching for recommended demos for performance.
        """
        search_query = request.args.get("search", "")
        today = date.today()
        # --- Recommended demos (cached) ---
        cache_key = "recommended_demos_v1"
        recommended_demos = None
        if hasattr(cache, "get") and callable(cache.get):
            recommended_demos = cache.get(cache_key)
        if recommended_demos is None:
            # Get recommended demo_ids from the recommended_demos collection
            recs = list(mongo.recommended_demos.find({}))
            demo_ids = [ObjectId(rec["demo_id"]) for rec in recs if "demo_id" in rec]
            # Fetch demos, filter for approved and not hidden, and not in the past
            demos = list(mongo.demonstrations.find({"_id": {"$in": demo_ids}, "approved": True, "hide": {"$ne": True}}))
            # Sort by recommend_till (date of demo)
            def get_recommend_till(d):
                rec = next((r for r in recs if str(r["demo_id"]) == str(d["_id"])), None)
                return rec["recommend_till"] if rec else d.get("date", "9999-12-31")
            demos.sort(key=get_recommend_till)
            # Remove past demos
            demos = [d for d in demos if datetime.strptime(d["date"], "%Y-%m-%d").date() >= today]
            recommended_demos = demos
            if hasattr(cache, "set") and callable(cache.set):
                cache.set(cache_key, recommended_demos, timeout=60*10)  # Cache for 10 min
        # --- Featured/other demos ---
        demonstrations = demonstrations_collection.find(DEMO_FILTER)
        filtered_demonstrations = []
        for demo in demonstrations:
            demo_date = datetime.strptime(demo["date"], "%Y-%m-%d").date()
            if demo_date >= today:
                if (
                    search_query.lower() in demo["title"].lower()
                    or search_query.lower() in demo["city"].lower()
                    or search_query.lower() in demo["address"].lower()
                ):
                    filtered_demonstrations.append(demo)
        filtered_demonstrations.sort(
            key=lambda x: datetime.strptime(x["date"], "%Y-%m-%d").date()
        )
        return render_template(
            "index.html",
            demonstrations=filtered_demonstrations,
            recommended_demos=recommended_demos,
        )

    @app.route("/terms")
    def terms():
        """
        Render the terms and conditions page.
        """
        return render_template("terms.html")
    
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
            # --- Submitter info fields ---
            submitter_role = request.form.get("submitter_role")
            submitter_email = request.form.get("submitter_email")
            submitter_name = request.form.get("submitter_name")
            accept_terms = request.form.get("accept_terms")
            # --- End submitter fields ---

            if img:
                    filename = secure_filename(img.filename)
                    bucket_name = "mielenosoitukset.fi"
                    # upload directly from the file storage stream to S3 (no disk)
                    photo_url = upload_image_fileobj(bucket_name, img.stream, filename, "demo_pics")
            # --- Add submitter info to required fields check ---
            if not title or not date or not start_time or not city or not address or not submitter_role or not submitter_email or not submitter_name or not accept_terms:
                flash_message("Ole hyvä, ja anna kaikki pakolliset tiedot sekä hyväksy käyttöehdot ja tietosuojaseloste.", "error")
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

            demo_dict = demonstration.to_dict()
            result = mongo.demonstrations.insert_one(demo_dict)
            demo_id = result.inserted_id

            # --- Save submitter info in separate collection ---
            submitter_doc = {
                "demonstration_id": demo_id,
                "submitter_role": submitter_role,
                "submitter_email": submitter_email,
                "submitter_name": submitter_name,
                "accept_terms": bool(accept_terms),
                "submitted_at": datetime.utcnow(),
            }
            submitters_collection.insert_one(submitter_doc)
            # --- End submitter info ---

            # --- Send confirmation email to submitter ---
            if submitter_email:
                email_sender.queue_email(
                    template_name="demo_submitter_confirmation.html",
                    subject="Kiitos mielenosoituksen ilmoittamisesta",
                    recipients=[submitter_email],
                    context={
                        "title": title,
                        "date": date,
                        "city": city,
                        "address": address,
                    },
                )

            # --- Notify support team with magic approve link ---
            from mielenosoitukset_fi.admin.admin_demo_bp import serializer, generate_demo_preview_link
            approve_token = serializer.dumps(str(demo_id), salt="approve-demo")
            approve_link = url_for("admin_demo.approve_demo_with_token", token=approve_token, _external=True)
            preview_link = generate_demo_preview_link(str(demo_id))
            # Generate a reject token and link (same as approve, but with a different salt and route)
            reject_token = serializer.dumps(str(demo_id), salt="reject-demo")
            reject_link = url_for("admin_demo.reject_demo_with_token", token=reject_token, _external=True)
            email_sender.queue_email(
                template_name="admin_demo_approve_notification.html",
                subject="Uusi mielenosoitus odottaa hyväksyntää",
                recipients=["tuki@mielenosoitukset.fi"],
                context={
                    "title": title,
                    "date": date,
                    "city": city,
                    "address": address,
                    "submitter_name": submitter_name,
                    "submitter_email": submitter_email,
                    "submitter_role": submitter_role,
                    "approve_link": approve_link,
                    "preview_link": preview_link,
                    "reject_link": reject_link,
                },
            )

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

        
        Parameters
        ----------
        None
        
        Returns
        -------
        response : flask.Response
            Renders the full list template or the demo cards partial if AJAX.
        """
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20) or 20)
        search_query = request.args.get("search", "").lower()
        city_query = request.args.get("city", "").lower()
        if "," in city_query:
            city_query = city_query.split(",")
        location_query = request.args.get("location", "").lower()
        date_query = request.args.get("date", "")
        today = date.today()
        demonstrations = demonstrations_collection.find(DEMO_FILTER)
        filtered_demonstrations = filter_demonstrations(demonstrations, today, search_query, city_query, location_query, date_query)
        filtered_demonstrations.sort(key=lambda x: datetime.strptime(x["date"], "%Y-%m-%d").date())
        total_demos = len(filtered_demonstrations)
        total_pages = (total_demos + per_page - 1) // per_page
        start = (page - 1) * per_page
        end = start + per_page
        paginated_demonstrations = filtered_demonstrations[start:end]
        # Return demo cards partial if AJAX request detected
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return render_template("demo_cards.html", demonstrations=paginated_demonstrations)
        return render_template("list.html", demonstrations=paginated_demonstrations, page=page, total_pages=total_pages, city_list=CITY_LIST)

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
            key=lambda x: datetime.strptime(x["date"], "%Y-%m-%d").date()
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
        demo_date = datetime.strptime(demo["date"], "%Y-%m-%d").date()
        return demo_date >= today

    def matches_filters(demo, search_query, city_query, location_query, date_query):
        """
        Check if the demonstration matches the filtering criteria.
        
        Parameters
        ----------
        demo : dict
            The demonstration document
        search_query : str
            Search term to filter by title and address
        city_query : str or list
            City or cities to filter by
        location_query : str
            Location to filter by address
        date_query : str
            Date range query in format 'YYYY-MM-DD,YYYY-MM-DD' or single date 'YYYY-MM-DD'
            
        Returns
        -------
        bool
            True if demo matches all filters, False otherwise
        """
        matches_search = (
            search_query in demo["title"].lower()
            or search_query in demo["address"].lower()
        )
        
        matches_city = (
            any(city in demo["city"].lower() for city in city_query)
            if isinstance(city_query, list)
            else city_query in demo["city"].lower()
        ) if city_query else True
        
        matches_location = (
            location_query in demo["address"].lower() if location_query else True
        )

        matches_date = True
        try:
            # Handle date range
            if request.args and request.args.get("date_start") and request.args.get("date_end"):
                start_date_str = request.args.get("date_start")
                end_date_str = request.args.get("date_end")
                try:
                    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                    demo_date = datetime.strptime(demo["date"], "%Y-%m-%d").date()
                    matches_date = start_date <= demo_date <= end_date
                except ValueError:
                    matches_date = True
    
        except ValueError:
            flash_message(
                _("Virheellinen päivämäärän muoto. Ole hyvä ja käytä muotoa vvvv-kk-pp.")
            )
            matches_date = False

        return matches_search and matches_city and matches_location and matches_date

    @app.route("/demonstration/<demo_id>")
    def demonstration_detail(demo_id):
        """
        Display details of a specific demonstration and save map coordinates if available.
        """
        #result = demonstrations_collection.find_one({"_id": ObjectId(demo_id)})
        demo = Demonstration.load_by_id(demo_id)
        if not demo:
            abort(404)
      
        if not demo:
            flash_message(
                _("Mielenosoitusta ei löytynyt tai sitä ei ole vielä hyväksytty."),
                "error",
            )
            return redirect(url_for("demonstrations"))
        
        if not demo.approved and not current_user.has_permission("VIEW_DEMO") or demo.hide and not current_user.has_permission("VIEW_DEMO"):
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
        _demo = copy.copy(demo)
        demo = Demonstration.to_dict(demo, True)
        log_demo_view(
            _demo._id, current_user._id if current_user.is_authenticated else None
        )
        return render_template("detail.html", demo=demo)

    @app.route("/demonstration/<demo_id>/some", methods=["GET"])
    @permission_required("VIEW_DEMO")
    @depracated_endpoint
    def preview(demo_id):
        """
        Display details of a specific demonstration and save map coordinates if available.
        
        .. deprecated:: 3.0
            This route will be removed in the next version.
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
        siblings.sort(key=lambda x: datetime.strptime(x.date, "%Y-%m-%d").date())
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
            
            flash_message("Yhteydenottopyyntö välitetty onnistuneesti!", "success")
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
            demo_date = datetime.strptime(demo["date"], "%Y-%m-%d").date()
            if demo_date >= today:
                upcoming_demos.append(demo)
        upcoming_demos.sort(
            key=lambda x: datetime.strptime(x["date"], "%Y-%m-%d").date()
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
    
    @app.route("/download_material/<demo_id>", methods=["GET"])
    def download_material(demo_id):
        
        return send_file(f"static/demo_preview/{demo_id}.png", as_attachment=True)
        
        if request.referrer != url_for("download_material"):
            flash_message("Virheellinen pyyntö.", "error")
            return redirect(url_for("index"))
        return render_template("download_material.html")

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

    @app.route("/subscribe_reminder/<demo_id>", methods=["POST"])
    def subscribe_reminder(demo_id):
        """
        Subscribe a user to demonstration reminders.

        Parameters
        ----------
        demo_id : str
            The demonstration ObjectId as a string.

        Returns
        -------
        flask.Response
            JSON response with status and message.
        """
        user_email = request.form.get("user_email")
        if not user_email:
            return jsonify({"status": "ERROR", "message": "Sähköpostiosoite vaaditaan."})
        reminders_collection = mongo["demo_reminders"]
        # Prevent duplicate subscriptions
        existing = reminders_collection.find_one({"demonstration_id": ObjectId(demo_id), "user_email": user_email})
        if existing:
            return jsonify({"status": "OK", "message": "Olet jo tilannut muistutuksen tälle mielenosoitukselle."})
        reminders_collection.insert_one({
            "demonstration_id": ObjectId(demo_id),
            "user_email": user_email,
            "created_at": datetime.utcnow(),
        })
        return jsonify({"status": "OK", "message": "Muistutus tilattu onnistuneesti!"})

    @app.route("/manifest.json")
    def manifest():
        """
        Serve the web app manifest file.
        """
        return send_from_directory(
            os.path.join(app.root_path, "static"), "manifest.json", mimetype="application/json"
        )
    
    add_api_routes(app)


