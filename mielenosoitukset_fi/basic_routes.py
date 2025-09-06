import copy
import os
import re
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta
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
from mielenosoitukset_fi.utils.database import DEMO_FILTER, stringify_object_ids
from mielenosoitukset_fi.utils.analytics import log_demo_view
from mielenosoitukset_fi.utils.wrappers import permission_required, depracated_endpoint
from mielenosoitukset_fi.utils.screenshot import trigger_screenshot
from werkzeug.utils import secure_filename
from mielenosoitukset_fi.a import generate_demo_sentence
from flask_caching import Cache  # New import for caching
from mielenosoitukset_fi.utils.logger import logger

email_sender = EmailSender()

# Initialize MongoDB
db_manager = DatabaseManager().get_instance()
mongo = db_manager.get_db()
demonstrations_collection = mongo["demonstrations"]
submitters_collection = mongo["submitters"]  # <-- Add this line
malicious_reports_collection = mongo["malicious_reports"]



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
            logger.exception(f"Error formatting time: {t}")
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
        "description": demo.get("description", ""),
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

    _cache = Cache(app, config={"CACHE_TYPE": "simple"})  # in-memory, fine for small scale
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
    
    from werkzeug.utils import secure_filename
    from datetime import datetime
    from mielenosoitukset_fi.utils.validators import valid_email
    from mielenosoitukset_fi.admin.admin_demo_bp import (
        generate_demo_approve_link,
        generate_demo_reject_link,
        generate_demo_preview_link,
    )
    # upload_image_fileobj, Organizer, Demonstration, flash_message, mongo, email_sender, CITY_LIST
    # should already be imported elsewhere in your app/module

    @app.route("/submit", methods=["GET", "POST"])
    def submit():
        """
        Handle submission of a new demonstration.

        Integrates with the hardened magic-link system:
        - Generates single-use, IP-bound approve/reject/preview links for admin use.
        """
        if request.method == "POST":
            # --- Basic fields ---
            title = (request.form.get("title") or "").strip()
            date = (request.form.get("date") or "").strip()
            description = (request.form.get("description") or "").strip()
            start_time = (request.form.get("start_time") or "").strip()
            end_time = (request.form.get("end_time") or "").strip() or None
            facebook = (request.form.get("facebook") or "").strip()
            city = (request.form.get("city") or "").strip()
            address = (request.form.get("address") or "").strip()
            event_type = (request.form.get("type") or "").strip()
            route = request.form.get("route") if event_type == "marssi" else None

            # --- Tags (comma separated) ---
            tags_field = request.form.get("tags", "")
            tags = [t.strip() for t in tags_field.split(",") if t.strip()] if tags_field else []

            # --- File upload (S3) ---
            img = request.files.get("image")
            photo_url = ""
            if img and getattr(img, "filename", ""):
                try:
                    filename = secure_filename(img.filename)
                    bucket_name = current_app.config.get("S3_BUCKET", "mielenosoitukset.fi")
                    s3_url = upload_image_fileobj(bucket_name, img.stream, filename, "demo_pics")
                    if s3_url:
                        photo_url = s3_url
                    else:
                        # upload failed but we don't block submitter; log and continue
                        logger.error("S3 upload failed for submit image: %s", filename)
                except Exception as e:
                    logger.exception("Error uploading image for demo submit: %s", e)

            # --- Submitter info fields ---
            submitter_role = (request.form.get("submitter_role") or "").strip()
            submitter_email = (request.form.get("submitter_email") or "").strip()
            submitter_name = (request.form.get("submitter_name") or "").strip()
            accept_terms = request.form.get("accept_terms")  # checkbox presence

            # --- Required validation --
            missing = []
            if not title:
                missing.append("otsikko")
            if not date:
                missing.append("päivämäärä")
            if not start_time:
                missing.append("alkamisaika")
            if not city:
                missing.append("kaupunki")
            if not address:
                missing.append("osoite")
            if not submitter_role:
                missing.append("rooli")
            if not submitter_email:
                missing.append("sähköposti")
            if not submitter_name:
                missing.append("nimi")
            if not accept_terms:
                missing.append("ehdot")

            if missing:
                flash_message(
                    "Ole hyvä, ja anna kaikki pakolliset tiedot sekä hyväksy käyttöehdot ja tietosuojaseloste. Puuttuvat kentät: "
                    + ", ".join(missing),
                    "error",
                )
                return redirect(url_for("submit"))

            # Validate email format
            if not valid_email(submitter_email):
                flash_message("Virheellinen sähköpostiosoite.", "error")
                return redirect(url_for("submit"))

            # --- Collect organizers ---
            organizers = []
            i = 1
            while True:
                name_field = request.form.get(f"organizer_name_{i}")
                if not name_field and f"organizer_name_{i}" not in request.form:
                    break
                organizers.append(
                    Organizer(
                        name=(name_field or "").strip(),
                        email=(request.form.get(f"organizer_email_{i}") or "").strip(),
                        website=(request.form.get(f"organizer_website_{i}") or "").strip(),
                    )
                )
                i += 1

            # --- Assemble Demonstration object ---
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

            # Save demonstration
            try:
                demo_dict = demonstration.to_dict()
                result = mongo.demonstrations.insert_one(demo_dict)
                demo_id = result.inserted_id
            except Exception as e:
                logger.exception("Failed to insert demonstration: %s", e)
                flash_message("Palvelinvirhe: mielenosoituksen tallentaminen epäonnistui.", "error")
                return redirect(url_for("submit"))

            # --- Save submitter info in separate collection ---
            try:
                submitter_doc = {
                    "demonstration_id": demo_id,
                    "submitter_role": submitter_role,
                    "submitter_email": submitter_email,
                    "submitter_name": submitter_name,
                    "accept_terms": bool(accept_terms),
                    "submitted_at": datetime.utcnow(),
                }
                mongo.submitters.insert_one(submitter_doc)
            except Exception as e:
                logger.exception("Failed to save submitter info: %s", e)
                # do not abort the workflow — demo exists, but warn admins
                flash_message("Varoitus: ilmoittajan tiedot eivät tallentuneet oikein.", "warning")

            # --- Send confirmation email to submitter ---
            try:
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
            except Exception as e:
                logger.exception("Failed to queue submitter confirmation email: %s", e)

            # --- Generate secure admin magic links (single-use, IP-bound) ---
            try:
                # generate_demo_* helpers will create registry records and return external URLs
                approve_link = generate_demo_approve_link(str(demo_id))
                preview_link = generate_demo_preview_link(str(demo_id))
                reject_link = generate_demo_reject_link(str(demo_id))
            except Exception as e:
                logger.exception("Failed to generate admin magic links: %s", e)
                approve_link = preview_link = reject_link = None

            # --- Notify support team with secure links ---
            try:
                ctx = {
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
                }
                email_sender.queue_email(
                    template_name="admin_demo_approve_notification.html",
                    subject="Uusi mielenosoitus odottaa hyväksyntää",
                    recipients=["tuki@mielenosoitukset.fi"],
                    context=ctx,
                )
            except Exception as e:
                logger.exception("Failed to queue admin notification email: %s", e)

            flash_message(
                "Mielenosoitus ilmoitettu onnistuneesti! Tiimimme tarkistaa sen, jonka jälkeen se tulee näkyviin sivustolle.",
                "success",
            )
            return redirect(url_for("index"))

        # GET — render submission form
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
        
        
        if _demo.recurs:
            toistuvuus = generate_demo_sentence(demo)

        else:
            toistuvuus = ""
        
        return render_template("detail.html", demo=demo, toistuvuus=toistuvuus)

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
        # Try to find the demonstration and use its S3/CDN preview_image if available
        try:
            # Accept both ObjectId and slug/running_number strings
            query = {
                "$or": [
                    {"_id": ObjectId(demo_id)},
                    {"slug": demo_id},
                    {"running_number": demo_id},
                ]
            }
        except Exception:
            query = {"$or": [{"slug": demo_id}, {"running_number": demo_id}]}

        demo = demonstrations_collection.find_one(query)
        if demo:
            preview_url = demo.get("preview_image") or demo.get("img")
            if preview_url and preview_url.startswith("http"):
                # Redirect to the CDN/S3 URL so the client can download directly
                return redirect(preview_url)

        # Fallback to a local static file if it exists
        local_path = os.path.join(app.root_path, "static", "demo_preview", f"{demo_id}.png")
        if os.path.exists(local_path):
            return send_file(local_path, as_attachment=True)

        flash_message(_("Esikatselukuva ei löytynyt."), "error")
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

    @app.route("/subscribe_reminder/<demo_id>", methods=["POST"])
    def subscribe_reminder(demo_id):
        user_email = request.form.get("user_email")
        user_ip = request.remote_addr
        user_agent = request.headers.get("User-Agent", "")

        if not user_email:
            return jsonify({"status": "ERROR", "message": "Sähköpostiosoite vaaditaan."})

        if not is_valid_email(user_email):
            report_malicious(
                ip=user_ip,
                reason="Invalid / potentially malicious email",
                user_email=user_email,
                demo_id=demo_id,
                user_agent=user_agent
            )
            return jsonify({"status": "ERROR", "message": "Sähköpostiosoite ei ole kelvollinen."})

        reminders_collection = mongo["demo_reminders"]

        # Prevent duplicate subscriptions
        existing = reminders_collection.find_one({
            "demonstration_id": ObjectId(demo_id),
            "user_email": user_email
        })
        if existing:
            return jsonify({"status": "OK", "message": "Olet jo tilannut muistutuksen tälle mielenosoitukselle."})

        # Rate limit by IP (max 5 per hour)
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_requests = reminders_collection.count_documents({
            "user_ip": user_ip,
            "created_at": {"$gte": one_hour_ago}
        })
        if recent_requests >= 10:
            report_malicious(
                ip=user_ip,
                reason="Too many reminder requests in 1 hour",
                user_email=user_email,
                demo_id=demo_id,
                user_agent=user_agent
            )
            return jsonify({"status": "ERROR", "message": "Liian monta pyyntöä tunnin sisällä, yritä myöhemmin."})

        # Insert reminder
        reminders_collection.insert_one({
            "demonstration_id": ObjectId(demo_id),
            "user_email": user_email,
            "user_ip": user_ip,
            "user_agent": user_agent,
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
    import xml.etree.ElementTree as ET
    from flask import Response, url_for
    from datetime import datetime
    from email.utils import format_datetime
    from bson import ObjectId
    import html


    def create_rss_feed(demonstrations):
        """
        Build an RSS 2.0 feed for demonstrations.
        """
        feed = ET.Element("rss", version="2.0")
        channel = ET.SubElement(feed, "channel")

        # Channel metadata
        ET.SubElement(channel, "title").text = "Mielenosoitukset"
        ET.SubElement(channel, "link").text = url_for("index", _external=True)
        ET.SubElement(channel, "description").text = "Viimeisimmät mielenosoitukset."
        ET.SubElement(channel, "language").text = "fi-fi"

        now = datetime.utcnow()
        ET.SubElement(channel, "pubDate").text = format_datetime(now)
        ET.SubElement(channel, "lastBuildDate").text = format_datetime(now)
        ET.SubElement(channel, "copyright").text = "© 2025 Mielenosoitukset.fi"
        for demo in demonstrations:
            item = ET.SubElement(channel, "item")

            demo_id = str(demo.get("_id", ""))
            demo_title = demo.get("title", "Tuntematon tapahtuma")
            demo_date = demo.get("formatted_date", "Tuntematon päivämäärä")
            demo_description = demo.get("description") or "Ei kuvausta."

            # Title
            ET.SubElement(item, "title").text = f"{demo_title} – {demo_date}"

            # Link + GUID
            link_url = url_for("demonstration_detail", demo_id=demo_id, _external=True)
            ET.SubElement(item, "link").text = link_url
            ET.SubElement(item, "guid", isPermaLink="true").text = link_url

            # Description (safe fallback)
            ET.SubElement(item, "description").text = html.escape(str(demo_description))

            # pubDate
            if "date" in demo and isinstance(demo["date"], datetime):
                ET.SubElement(item, "pubDate").text = format_datetime(demo["date"])

        # Return pretty UTF-8 XML string
        return ET.tostring(feed, encoding="utf-8", xml_declaration=True)

    from flask import Response, url_for, request
    from datetime import datetime
    import hashlib

    @app.route("/demonstrations.rss")
    @_cache.cached(timeout=300)  # cache for 5 minutes
    def demonstrations_rss():
        """
        Serve the RSS feed for demonstrations.
        Cached heavily to reduce DB load.
        """
        demonstrations = list(
            demonstrations_collection.find().sort("date", -1).limit(50)
        )

        # Normalize ObjectId → str
        for demo in demonstrations:
            if "_id" in demo and isinstance(demo["_id"], ObjectId):
                demo["_id"] = str(demo["_id"])

        feed_xml = create_rss_feed(demonstrations)

        # Create ETag for conditional GET
        etag = hashlib.md5(feed_xml).hexdigest()
        last_modified = datetime.utcnow()

        # Check if client already has this version
        if request.headers.get("If-None-Match") == etag:
            return Response(status=304)

        return Response(
            feed_xml,
            mimetype="application/rss+xml",
            headers={
                "Cache-Control": "public, max-age=300, must-revalidate",
                "ETag": etag,
                "Last-Modified": last_modified.strftime("%a, %d %b %Y %H:%M:%S GMT"),
                "Content-Type": "application/rss+xml; charset=utf-8",
            },
        )
    from datetime import datetime, date
    from collections import defaultdict
    import calendar
    from flask import render_template

    # ============================
    # Month view
    # ============================
    @app.route("/calendar/")
    @app.route("/calendar/<int:year>/<int:month>/")
    def calendar_month_view(year=None, month=None):
        today = date.today()
        if year is None or month is None:
            year, month = today.year, today.month

        # Haetaan kaikki demonstraatiot
        demonstrations = list(demonstrations_collection.find())

        # Filteröidään vain kyseisen kuukauden demoja
        month_demos = defaultdict(list)
        for demo in demonstrations:
            demo_date = demo.get("date")
            if demo_date:
                dd = datetime.strptime(demo_date, "%Y-%m-%d").date()
                if dd.year == year and dd.month == month:
                    month_demos[dd.day].append(demo)

        # Kalenteri kuukaudelle
        cal = calendar.Calendar(firstweekday=0)  # 0 = Monday
        month_days = cal.monthdayscalendar(year, month)  # list of weeks, 0 = päivä ei ole tässä kuussa

        # Edellinen ja seuraava kuukausi
        prev_month = month - 1 or 12
        prev_year = year - 1 if month == 1 else year
        next_month = month + 1 if month != 12 else 1
        next_year = year + 1 if month == 12 else year

        # Kuukausien nimet
        month_names = {
            1: "Tammikuu", 2: "Helmikuu", 3: "Maaliskuu", 4: "Huhtikuu",
            5: "Toukokuu", 6: "Kesäkuu", 7: "Heinäkuu", 8: "Elokuu",
            9: "Syyskuu", 10: "Lokakuu", 11: "Marraskuu", 12: "Joulukuu",
        }

        return render_template(
            "demo_views/calendar_grid.html",
            year=year,
            month=month,
            month_name=month_names[month],
            month_days=month_days,
            month_demos=month_demos,
            prev_year=prev_year,
            prev_month=prev_month,
            next_year=next_year,
            next_month=next_month
        )

    # ============================
    # Year view
    # ============================
    @app.route("/calendar/<int:year>/")
    def calendar_year_view(year):
        # Haetaan kaikki demonstraatiot
        demonstrations = list(demonstrations_collection.find())

        # Valmistellaan tietorakenne: month -> {weeks, days}
        year_demos = {}
        cal = calendar.Calendar(firstweekday=0)  # Monday
        for month in range(1, 13):
            month_weeks = cal.monthdayscalendar(year, month)
            year_demos[month] = {
                "weeks": month_weeks,
                "days": defaultdict(list)
            }

        # Lisätään demoja oikeille päiville
        for demo in demonstrations:
            demo_date_str = demo.get("date")
            if demo_date_str:
                dd = datetime.strptime(demo_date_str, "%Y-%m-%d").date()
                if dd.year == year:
                    year_demos[dd.month]["days"][dd.day].append(demo)

        # Kuukausien nimet
        month_names = {
            1: "Tammikuu", 2: "Helmikuu", 3: "Maaliskuu", 4: "Huhtikuu",
            5: "Toukokuu", 6: "Kesäkuu", 7: "Heinäkuu", 8: "Elokuu",
            9: "Syyskuu", 10: "Lokakuu", 11: "Marraskuu", 12: "Joulukuu",
        }

        return render_template(
            "demo_views/calendar_year.html",
            year=year,
            month_names=month_names,
            year_demos=year_demos
        )

    @app.context_processor
    def inject_current_year():
        return dict(current_year=datetime.now().year)



    from datetime import datetime

    def report_malicious(ip, reason, user_email=None, demo_id=None, user_agent=None):
        """
        Logs a suspicious/malicious activity in the malicious_traffic collection.

        Parameters
        ----------
        ip : str
            IP address of the requester
        reason : str
            Why the traffic was flagged
        user_email : str, optional
            Email used in the request
        demo_id : str or ObjectId, optional
            Demonstration id related to the request
        user_agent : str, optional
            User-Agent string
        """
        doc = {
            "ip": ip,
            "reason": reason,
            "user_email": user_email,
            "demo_id": demo_id if isinstance(demo_id, str) else str(demo_id) if demo_id else None,
            "user_agent": user_agent,
            "reported_at": datetime.utcnow(),
        }
        malicious_reports_collection.insert_one(doc)

    import re

    EMAIL_REGEX = r"^[\w\.\-]+@[\w\-]+\.[a-zA-Z]{2,}$"

    def is_valid_email(email):
        """
        Checks if the email is valid and doesn’t contain suspicious characters.
        """
        if not re.match(EMAIL_REGEX, email):
            return False
        # Additional blacklist for characters that could be used in injection
        suspicious_chars = ["$", "{", "}", ";", "--", "'", "\""]
        if any(char in email for char in suspicious_chars):
            return False
        return True

