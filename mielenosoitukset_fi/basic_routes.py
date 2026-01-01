import copy
import math
import os
import re
import json
import threading
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta
from flask_babel import _, refresh
from flask import (
    app,
    g,
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
from flask_login import current_user, login_required
from bson.objectid import ObjectId
from mielenosoitukset_fi.utils.notifications import fetch_notifications
from mielenosoitukset_fi.utils.s3 import upload_image_fileobj
from mielenosoitukset_fi.utils.classes import Organizer, Demonstration, Organization, RecurringDemonstration
from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.emailer.EmailSender import EmailSender
from mielenosoitukset_fi.utils.variables import CITY_LIST
from mielenosoitukset_fi.utils.flashing import flash_message
from mielenosoitukset_fi.utils.database import DEMO_FILTER, stringify_object_ids
from mielenosoitukset_fi.utils.analytics import log_demo_view
from mielenosoitukset_fi.utils.wrappers import admin_required, permission_required, depracated_endpoint
from mielenosoitukset_fi.utils.screenshot import trigger_screenshot
from werkzeug.utils import secure_filename
from mielenosoitukset_fi.a import generate_demo_sentence

from mielenosoitukset_fi.utils.cache import cache
from mielenosoitukset_fi.utils.logger import logger
from mielenosoitukset_fi.utils.classes import Case
from mielenosoitukset_fi.utils.demo_cancellation import (
    cancel_demo,
    fetch_cancellation_token,
    mark_token_used,
    queue_cancellation_links_for_demo,
    request_cancellation_case,
)

email_sender = EmailSender()

# Initialize MongoDB
db_manager = DatabaseManager().get_instance()
mongo = db_manager.get_db()
demonstrations_collection = mongo["demonstrations"]
submitters_collection = mongo["submitters"]  # <-- Add this line
malicious_reports_collection = mongo["malicious_reports"]

PANIC_MODE = False


def _load_panic():
    a = mongo.panic.find_one({"name": "global"})
    return a.get("panic", False) if a else False

PANIC_MODE = _load_panic()

def refresh_panic(interval=15):  # 180 seconds = 3 minutes
    global PANIC_MODE
    while True:
        PANIC_MODE = _load_panic()
        time.sleep(interval)

# Start background thread
threading.Thread(target=refresh_panic, daemon=True).start()
    

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
        
    def _get_demo_img(demo):
        """
        Get the demonstration image URL.

        Parameters
        ----------
        demo : dict

        Returns
        -------
        str
        """
        return demo.get("img") or demo.get("preview_image") or demo.get("cover_image") or "#"

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
        "cover_image": _get_demo_img(demo),
        "cancelled": bool(demo.get("cancelled")),
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
        if demo.get("cancelled"):
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

    @app.route("/api/v1/check_demo_conflict", methods=["GET"])
    def api_check_demo_conflict():
        """
        AJAX endpoint to check for similar demonstrations given title/date/city/address.

        Query params: title, date (YYYY-MM-DD), city, address
        Returns JSON: { matches: [ { _id, title, address, date } ... ] }
        """
        title = (request.args.get('title') or '').strip()
        date_q = (request.args.get('date') or '').strip()
        city_q = (request.args.get('city') or '').strip()
        address_q = (request.args.get('address') or '').strip()

        if not date_q or not city_q or not title:
            return jsonify(matches=[])

        try:
            potential = demonstrations_collection.find({
                "city": city_q,
                "date": date_q,
                "cancelled": {"$ne": True},
                "hide": {"$ne": True},
                "approved": True,
            })
            matches = []
            title_words = set([w for w in re.findall(r"\w+", title.lower()) if len(w) > 3])
            for d in potential:
                if len(matches) >= 5:
                    break
                existing_title = (d.get('title') or '').lower()
                existing_addr = (d.get('address') or '').lower()
                matched = False
                if title.lower() in existing_title or existing_title in title.lower():
                    matched = True
                else:
                    existing_words = set([w for w in re.findall(r"\w+", existing_title) if len(w) > 3])
                    if title_words and len(title_words & existing_words) >= 2:
                        matched = True
                if not matched and address_q:
                    if address_q.lower() in existing_addr or existing_addr in address_q.lower():
                        matched = True
                if matched:
                    matches.append({
                        "_id": str(d.get('_id')),
                        "title": d.get('title'),
                        "address": d.get('address'),
                        "date": d.get('date'),
                    })
            return jsonify(matches=matches)
        except Exception:
            logger.exception("Error while checking demo conflicts")
            return jsonify(matches=[])


def init_routes(app):
    from mielenosoitukset_fi.utils.cache import cache
    
    
    
    # register genereate_demo_sentence function
    @app.context_processor
    def inject_demo_sentence():
        return dict(generate_demo_sentence=generate_demo_sentence)

    from flask import Response

    @app.route("/robots.txt")
    def robots_txt():
        txt = """User-agent: *
    Disallow: /admin/
    Disallow: /users/auth/login/
    Disallow: /users/auth/register/
    Disallow: /users/auth/forgot/
    """
        return Response(txt, mimetype="text/plain")

        
    from flask import Response, url_for
    import xml.etree.ElementTree as ET
    from flask import Flask, Response, url_for
    import xml.etree.ElementTree as ET

    @app.route("/sitemap.xml", methods=["GET"])
    def sitemap():
        """
        Generate sitemap XML including hreflang alternate links.

        Notes
        -----
        Default language is Finnish. If only Finnish is enabled in
        BABEL_SUPPORTED_LOCALES, no alternate hreflang links are emitted.

        Returns
        -------
        flask.Response
            XML sitemap response (application/xml) or 500 on error.
        """
        try:
            # Supported locales (fallback to Finnish)
            locales = app.config.get("BABEL_SUPPORTED_LOCALES") or ["fi"]
            locales = [l for l in locales if l]  # normalize

            # If only Finnish is available, do not include alternate links
            include_alternates = not (
                len(locales) == 1 and locales[0].lower().startswith("fi")
            )

            # Use the official sitemap namespace and the xhtml namespace for alternate links
            ns_attribs = {
                "xmlns": "http://www.sitemaps.org/schemas/sitemap/0.9",
                "xmlns:xhtml": "http://www.w3.org/1999/xhtml",
            }
            urlset = ET.Element("urlset", ns_attribs)

            # Static endpoints to include
            static_routes = [
                {"loc": "index"},
                {"loc": "submit"},
                {"loc": "demonstrations"},
                {"loc": "info"},
                {"loc": "privacy"},
                {"loc": "contact"},
                {"loc": "campaign.index"},
            ]

            # Helper to add url + optional alternate links
            def _add_url_with_alternates(parent, endpoint, **values):
                url_el = ET.SubElement(parent, "url")
                loc_el = ET.SubElement(url_el, "loc")
                loc_el.text = url_for(endpoint, _external=True, **values)
                if include_alternates:
                    for lang in locales:
                        ET.SubElement(
                            url_el,
                            "{http://www.w3.org/1999/xhtml}link",
                            {
                                "rel": "alternate",
                                "hreflang": lang,
                                "href": url_for(
                                    endpoint, lang_code=lang, _external=True, **values
                                ),
                            },
                        )

            # Add static routes
            for r in static_routes:
                _add_url_with_alternates(urlset, r["loc"])

            # Demonstration URLs: limit to demos in reasonable date window
            query_filter = DEMO_FILTER.copy()
            start_date = (date.today() - timedelta(days=365)).strftime("%Y-%m-%d")
            end_date = (date.today() + timedelta(days=365 * 2)).strftime("%Y-%m-%d")
            query_filter["date"] = {"$gte": start_date, "$lte": end_date}

            def _format_lastmod_for_demo(demo):
                """
                Determine a suitable lastmod value for a demo.

                The function prefers explicit timestamp fields (updated_at, modified_at, ...)
                and falls back to the demo.date field. When an explicit timestamp is found
                it is normalized to a date string in "YYYY-MM-DD" form. If only a date
                string is available, it is returned as-is. Returns None if no sensible
                value is found.

                Parameters
                ----------
                demo : dict
                    Demonstration document.

                Returns
                -------
                str or None
                    ISO date string "YYYY-MM-DD" or original date-like string, or None.
                """
                candidates = (
                    "updated_at",
                    "modified_at",
                    "last_modified",
                    "lastmod",
                    "updated",
                    "modified",
                )

                def _to_date_str(v):
                    """Try to produce a YYYY-MM-DD string from v, or return None."""
                    if v is None:
                        return None
                    # datetime instance -> date string
                    try:
                        if isinstance(v, datetime):
                            return v.date().isoformat()
                    except Exception:
                        pass
                    # date instance -> isoformat
                    try:
                        if isinstance(v, date):
                            return v.isoformat()
                    except Exception:
                        pass
                    # string -> try parsing ISO/datetime/date formats
                    if isinstance(v, str):
                        s = v.strip()
                        if not s:
                            return None
                        # Handle common trailing Z timezone
                        try:
                            iso_s = s.replace("Z", "+00:00") if s.endswith("Z") else s
                            dt = datetime.fromisoformat(iso_s)
                            return dt.date().isoformat()
                        except Exception:
                            pass
                        # Try date-only format
                        try:
                            dt = datetime.strptime(s, "%Y-%m-%d")
                            return dt.date().isoformat()
                        except Exception:
                            pass
                        # Try datetime without timezone but with T
                        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                            try:
                                dt = datetime.strptime(s, fmt)
                                return dt.date().isoformat()
                            except Exception:
                                continue
                        # As a last resort return the original string (fallback consumer may handle)
                        return s
                    return None

                # Prefer explicit timestamp-like fields and always normalize to YYYY-MM-DD when possible
                for key in candidates:
                    v = demo.get(key)
                    if not v:
                        continue
                    date_str = _to_date_str(v)
                    if date_str:
                        return date_str

                # Fallback to demo['date']
                v = demo.get("date")
                if v:
                    date_str = _to_date_str(v)
                    if date_str:
                        return date_str
                    # if it's something else, return as-is
                    if isinstance(v, str) and v.strip():
                        return v
                return None

            for demo in demonstrations_collection.find(query_filter):
                demo_identifier = (
                    demo.get("slug")
                    or demo.get("running_number")
                    or str(demo.get("_id"))
                )
                url_el = ET.SubElement(urlset, "url")
                loc_el = ET.SubElement(url_el, "loc")
                loc_el.text = url_for(
                    "demonstration_detail", demo_id=demo_identifier, _external=True
                )

                # lastmod for the demonstration if available
                lastmod_val = _format_lastmod_for_demo(demo)
                if lastmod_val:
                    ET.SubElement(url_el, "lastmod").text = lastmod_val

                if include_alternates:
                    for lang in locales:
                        ET.SubElement(
                            url_el,
                            "{http://www.w3.org/1999/xhtml}link",
                            {
                                "rel": "alternate",
                                "hreflang": lang,
                                "href": url_for(
                                    "demonstration_detail",
                                    demo_id=demo_identifier,
                                    lang_code=lang,
                                    _external=True,
                                ),
                            },
                        )

            xml_bytes = ET.tostring(urlset, encoding="utf-8", xml_declaration=True)
            resp = Response(xml_bytes, mimetype="application/xml")
            resp.headers["Content-Type"] = "application/xml; charset=utf-8"
            return resp

        except Exception:
            app.logger.exception("Error generating sitemap")
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

            # Fetch demos, filter for approved and not hidden
            demos = list(
                mongo.demonstrations.find({
                    "_id": {"$in": demo_ids},
                    "approved": True,
                    "hide": {"$ne": True},
                    "cancelled": {"$ne": True},
                })
            )

            # Sort by recommend_till (or fallback to date)
            def get_recommend_till(d):
                rec = next((r for r in recs if str(r["demo_id"]) == str(d["_id"])), None)
                return rec["recommend_till"] if rec else d.get("date", "9999-12-31")

            demos.sort(key=get_recommend_till)

            # Remove past demos
            demos = [
                d for d in demos
                if datetime.strptime(d["date"], "%Y-%m-%d").date() >= today
            ]

            recommended_demos = demos

            if hasattr(cache, "set") and callable(cache.set):
                cache.set(cache_key, recommended_demos, timeout=60 * 10)  # Cache 10 min

        # --- Featured / other demos ---
        demonstrations = demonstrations_collection.find(DEMO_FILTER)
        filtered_demonstrations = [
            demo
            for demo in demonstrations
            if not demo.get("cancelled")
            if datetime.strptime(demo["date"], "%Y-%m-%d").date() >= today
        ]
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

    @app.route("/api/v1/search_organizations", methods=["GET"])
    def search_organizations():
        """
        Search for existing organizations by name.
        
        Query parameters:
        - q: search query (organization name)
        
        Returns JSON array of matching organizations with id, name, email, website.
        """
        query = (request.args.get("q") or "").strip()
        
        if not query or len(query) < 2:
            return jsonify([])
        
        # Search in organizations collection using case-insensitive regex
        mongo = DatabaseManager().get_instance().get_db()
        organizations = mongo["organizations"].find(
            {
                "name": {"$regex": query, "$options": "i"}
            },
            {"_id": 1, "name": 1, "email": 1, "website": 1, "description": 1}
        ).limit(10)
        
        results = []
        for org in organizations:
            results.append({
                "id": str(org["_id"]),
                "name": org.get("name", ""),
                "email": org.get("email", ""),
                "website": org.get("website", ""),
                "description": org.get("description", "")[:100] + "..." if len(org.get("description", "")) > 100 else org.get("description", "")
            })
        
        return jsonify(results)

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
            # checkbox presence: normalize to boolean
            accept_terms = bool(request.form.get("accept_terms"))

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
                # If this is an AJAX submission, return JSON instead of redirect
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify(success=False, message=("Puuttuvat kentät: " + ", ".join(missing))), 400
                return redirect(url_for("submit"))

            # Validate email format
            if not valid_email(submitter_email):
                flash_message("Virheellinen sähköpostiosoite.", "error")
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify(success=False, message="Virheellinen sähköpostiosoite."), 400
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

            # --- Check for similar demonstrations on same date/city to avoid duplicates ---
            force_submit = bool(request.form.get('force_submit'))
            if not force_submit:
                try:
                    potential = demonstrations_collection.find({
                        "city": city,
                        "date": date,
                        "cancelled": {"$ne": True},
                    })
                    matches = []
                    title_words = set([w for w in re.findall(r"\w+", title.lower()) if len(w) > 3])
                    for d in potential:
                        existing_title = (d.get('title') or '').lower()
                        existing_addr = (d.get('address') or '').lower()
                        # direct substring check
                        if title.lower() in existing_title or existing_title in title.lower():
                            matches.append(d)
                            continue
                        # word intersection heuristic
                        existing_words = set([w for w in re.findall(r"\w+", existing_title) if len(w) > 3])
                        if title_words and len(title_words & existing_words) >= 2:
                            matches.append(d)
                            continue
                        # address similarity
                        if address and (address.lower() in existing_addr or existing_addr in address.lower()):
                            matches.append(d)
                            continue
                    if matches:
                        # if AJAX, return structured JSON so frontend can prompt user
                        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                            short = [
                                {
                                    "_id": str(x.get("_id")),
                                    "title": x.get("title"),
                                    "address": x.get("address"),
                                    "date": x.get("date"),
                                }
                                for x in matches
                            ]
                            return jsonify(success=False, conflict=True, message="Löytyi samankaltaisia ilmoituksia tälle päivälle.", demos=short), 409
                        # otherwise, flash and redirect back to form
                        flash_message("Löytyi samankaltaisia ilmoituksia tälle päivälle. Ole hyvä ja tarkista ennen julkaisua.", "warning")
                        return redirect(url_for("submit"))
                except Exception:
                    # on any error in matching, continue with the normal flow
                    logger.exception("Error checking for existing similar demonstrations")


            # Save demonstration
            try:
                demo_dict = demonstration.to_dict()
                demonstration.save()
                #result = mongo.demonstrations.insert_one(demo_dict)
                demo_id = demonstration._id
            except Exception as e:
                logger.exception("Failed to insert demonstration: %s", e)
                flash_message("Palvelinvirhe: mielenosoituksen tallentaminen epäonnistui.", "error")
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify(success=False, message="Palvelinvirhe: tallentaminen epäonnistui."), 500
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

             # --- Create Admin Case ---
            try:
                Case.create_new(
                    case_type="new_demo",
                    demo_id=demo_id,
                    submitter=submitter_doc,
                    submitter_id=current_user._id if current_user else None, # or ObjectId of submitter doc if you want
                    meta={"urgency": "high"}  # optional, can be extended
                )
            except Exception as e:
                logger.exception("Failed to create admin case: %s", e)
            
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

            # --- Send organiser cancellation links ---
            try:
                queue_cancellation_links_for_demo(demonstration.to_dict(json=False))
            except Exception:
                logger.exception("Failed to queue cancellation links for demo %s", demo_id)

            flash_message(
                "Mielenosoitus ilmoitettu onnistuneesti! Tiimimme tarkistaa sen, jonka jälkeen se tulee näkyviin sivustolle.",
                "success",
            )
            # If AJAX, return JSON success so frontend can show the success page without following redirects
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify(success=True, message="Mielenosoitus ilmoitettu onnistuneesti!"), 200
            return redirect(url_for("index"))

        # Determine whether the current user is allowed to use test-mode autofill
        try:
            user_role = getattr(current_user, 'role', None)
        except Exception:
            user_role = None
        test_mode_allowed = bool(current_user.is_authenticated and user_role in ("admin", "global_admin"))
        # Determine whether current user can edit demonstrations
        try:
            can_edit_demo = bool(current_user.is_authenticated and current_user.has_permission("EDIT_DEMO"))
        except Exception:
            can_edit_demo = False

        # GET — render submission form
        return render_template("submit.html", city_list=CITY_LIST, test_mode_allowed=test_mode_allowed, can_edit_demo=can_edit_demo)


    @app.route("/report", methods=["GET", "POST"])
    def report():
        """
        Handle submission of a new error report.
        """
        error = request.form.get("error")  # Description of the error being reported
        _type = request.form.get("type")  # Type of the report (e.g., demonstration)
        mark_cancelled = bool(request.form.get("mark_cancelled"))
        reporter_email = (request.form.get("reporter_email") or "").strip() or None

        demo_oid = None
        try:
            demo_oid = ObjectId(request.form.get("demo_id")) if request.form.get("demo_id") else None
        except Exception:
            demo_oid = None

        if _type:
            if _type == "demonstration":
                report_doc = {
                    "error": error,
                    "demo_id": demo_oid,
                    "date": datetime.now(),
                    "user": (
                        ObjectId(current_user._id)
                        if current_user.is_authenticated
                        else None
                    ),
                    "ip": request.remote_addr,
                }
                if mark_cancelled:
                    report_doc["cancelled_reported"] = True
                if reporter_email:
                    report_doc["reporter_email"] = reporter_email
                mongo.reports.insert_one(report_doc)

            # new case from report
            try:
                Case.create_new(
                    case_type="demo_error_report",
                    demo_id=demo_oid if _type == "demonstration" else None,
                    submitter_id=current_user._id if current_user.is_authenticated else None,
                    meta={
                        "urgency": "low",
                        "report_type": _type,
                        "error": error,
                        "reported_cancelled": mark_cancelled,
                        "reporter_email": reporter_email,
                    },
                    error_report={
                        "error": error,
                        "demo_id": demo_oid,
                        "date": datetime.now(),
                        "user": (
                            ObjectId(current_user._id)
                            if current_user.is_authenticated
                            else None
                        ),
                        "ip": request.remote_addr,
                        "reported_cancelled": mark_cancelled,
                        "reporter_email": reporter_email,
                    }
                )

                if mark_cancelled and _type == "demonstration" and demo_oid:
                    demo_doc = mongo.demonstrations.find_one({"_id": demo_oid})
                    if demo_doc:
                        request_cancellation_case(
                            demo_doc,
                            reason=error,
                            requester_email=reporter_email,
                            official_contact=False,
                            source="user_report",
                        )
            except Exception as e:
                logger.exception("Failed to create case from error report: %s", e)

        else:
            mongo.reports.insert_one(
                {
                    "error": error,
                    "date": datetime.now(),
                    "user": current_user._id if current_user.is_authenticated else None,
                    "ip": request.remote_addr,
                    "reported_cancelled": mark_cancelled,
                    "reporter_email": reporter_email,
                }
            )

        flash_message(
            "Virhe ilmoitettu onnistuneesti! Kiitos ilmoituksestasi.", "success"
        )
        return redirect(request.referrer) # TODO: validate referrer?

    @app.route("/demonstrations")
    def demonstrations():
        """
        Render the demonstrations listing page.

        This route serves the main demonstrations listing interface, which loads 
        the `list copy.html` template. The page itself handles all search, filter, 
        and pagination logic on the client side via JavaScript — fetching data 
        dynamically from the API and rendering demonstration cards.

        The backend does not perform any filtering or data processing here; it only 
        delivers the static page shell that initializes the client-side functionality.

        Returns
        -------
        flask.Response
            Rendered HTML page (`list copy.html`), which serves as the frontend 
            container for dynamic demonstration listings.
        """
        return render_template("list copy.html")


    @app.route("/city/<city>") # TODO: lets make this use the api too
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
            if demo.get("cancelled"):
                continue
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
    from flask import make_response

    def _force_reload():
        # if theres fore_reload in the url, force cache bypass
        if "force_reload" in request.args:
            return True
        return False

    @app.route("/demonstration/<demo_id>")
    def demonstration_detail(demo_id):
        """
        Display demonstration detail with a cached HTML response and a reliable X-Cache header.

        The view uses the app cache manually so we can detect cache hits and set the
        X-Cache response header accordingly. Caching is bypassed when:
        - there is a query string
        - the current_user has VIEW_DEMO permission (admins)
        """
        # Load demonstration and permission checks first (so we don't serve cached 401/404)
        try:
            demo_obj = Demonstration.load_by_id(demo_id)
        except ValueError:
            abort(404)
        if not demo_obj:
            abort(404)

        if (not demo_obj.approved and not current_user.has_permission("VIEW_DEMO")) or \
            (demo_obj.hide and not current_user.has_permission("VIEW_DEMO")):
            abort(401)

        # Determine whether to bypass cache
        bypass_cache = bool(request.query_string) or (
            current_user.is_authenticated and current_user.has_permission("VIEW_DEMO")
        )

        # Build a cache key that is stable for public users; include locale so localized pages differ
        locale = session.get("locale", "")
        cache_key = f"demonstration_detail:v1:{demo_id}:locale={locale}"

        # Try to serve from cache if allowed
        if not bypass_cache and hasattr(cache, "get"):
            cached = cache.get(cache_key)
            if cached:
                # still log the view for analytics even when serving cached HTML
                try:
                    log_demo_view(demo_id, current_user._id if current_user.is_authenticated else None)
                except Exception:
                    logger.exception("Failed to log demo view for cached response")


                resp = Response(cached["data"], status=cached.get("status", 200), mimetype=cached.get("mimetype"))
                # restore headers (skip over Content-Length to allow Flask to recalc)
                for k, v in cached.get("headers", []):
                    if k.lower() == "content-length":
                        continue
                    resp.headers[k] = v
                resp.headers["X-Cache"] = "HIT (cached)"
                return resp

        # Not cached (or bypassed) — ensure we have coordinates if needed
        if not demo_obj.longitude:
            try:
                fetch_geocode_data(demo_obj)
            except Exception:
                logger.exception("Error fetching geocode for demo %s", demo_id)

        # Prepare response
        _demo = copy.copy(demo_obj)
        demo = Demonstration.to_dict(demo_obj, True)
        try:
            log_demo_view(_demo._id, current_user._id if current_user.is_authenticated else None)
        except Exception:
            logger.exception("Failed to log demo view")

        toistuvuus = ""
        if _demo.recurs:
            toistuvuus = generate_demo_sentence(demo)

        response = make_response(render_template("detail.html", demo=demo, toistuvuus=toistuvuus))
        response.headers["X-Cache"] = "MISS"

        # Store response in cache for future requests (if available)
        if not bypass_cache and hasattr(cache, "set"):
            try:
                # Capture headers as list of tuples
                headers_snapshot = list(response.headers.items())
                cache.set(
                    cache_key,
                    {
                        "data": response.get_data(),
                        "mimetype": response.mimetype,
                        "status": response.status_code,
                        "headers": headers_snapshot,
                    },
                    timeout=60 * 5,
                )
            except Exception:
                logger.exception("Failed to cache demonstration_detail for %s", demo_id)

        return response

    @app.route('/suggest_change/<demo_id>', methods=['GET', 'POST'])
    def suggest_change(demo_id):
        """
        Allow users to suggest changes to an existing demonstration.

        GET: render a small form showing demo info + textarea for suggestion
        POST: store suggestion in `demo_suggestions` collection and notify admins via flash/email
        """
        try:
            demo_doc = demonstrations_collection.find_one({"_id": ObjectId(demo_id)})
        except Exception:
            demo_doc = None

        if not demo_doc:
            flash_message("Mielenosoitusta ei löytynyt.", "error")
            return redirect(url_for('index'))

        if request.method == 'POST':
            # Collect candidate fields that the user may suggest changes for
            candidate_fields = [
                'title',
                'date',
                'start_time',
                'end_time',
                'city',
                'address',
                'facebook',
                'description',
                'tags',
                'route',
            ]

            suggested_fields = {}
            original_values = {}
            for f in candidate_fields:
                val = (request.form.get(f) or '').strip()
                # normalize tags as list if provided
                if f == 'tags' and val:
                    val_list = [t.strip() for t in val.split(',') if t.strip()]
                    val = val_list

                # compare to the stored demo_doc values and only store differences
                orig = demo_doc.get(f)
                # normalize original tags to list for comparison
                if f == 'tags' and isinstance(orig, list):
                    orig_comp = [str(x).strip() for x in orig]
                else:
                    orig_comp = (orig or '').strip() if orig is not None else ''

                # For comparison, when tags -> convert to list
                changed = False
                if f == 'tags':
                    if val and isinstance(val, list) and val != orig_comp:
                        changed = True
                else:
                    if val and str(val) != str(orig_comp):
                        changed = True

                if changed:
                    suggested_fields[f] = val
                    original_values[f] = orig

            reporter_email = (request.form.get('reporter_email') or '').strip() or None
            reporter_comment = (request.form.get('reporter_comment') or '').strip() or None

            if not suggested_fields and not reporter_comment:
                flash_message("Kirjoita vähintään yksi kenttämuutos tai kommentti ennen lähettämistä.", "error")
                return redirect(request.url)

            doc = {
                'demo_id': str(demo_id),
                'suggested_fields': suggested_fields,
                'original_values': original_values,
                'reporter_comment': reporter_comment,
                'reporter_email': reporter_email,
                'created_at': datetime.utcnow(),
                'ip': request.remote_addr,
                'user_agent': request.headers.get('User-Agent'),
                'status': 'new',
            }
            try:
                mongo.demo_suggestions.insert_one(doc)
                flash_message('Ehdotuksesi on vastaanotettu. Kiitos!', 'success')
                # queue an email to admins with details
                try:
                    email_sender.queue_email(
                        template_name='admin_suggestion_notification.html',
                        subject=f'Uusi ehdotus mielenosoitukselle: {demo_doc.get("title")}',
                        recipients=['tuki@mielenosoitukset.fi'],
                        context={'demo': demo_doc, 'suggestion_doc': doc},
                    )
                except Exception:
                    logger.exception('Failed to queue suggestion notification email')
            except Exception:
                logger.exception('Failed to save suggestion')
                flash_message('Palvelinvirhe: ehdotuksen tallentaminen epäonnistui.', 'error')
                return redirect(request.url)

            return redirect(url_for('demonstration_detail', demo_id=demo_id))

        # GET — render form with per-field inputs
        demo = Demonstration.from_dict(demo_doc)
        return render_template('suggest_change.html', demo=demo)

    @app.route("/cancel_demonstration/<token>", methods=["GET", "POST"])
    def cancel_demo_with_token(token):
        token_error = None
        token_doc = fetch_cancellation_token(token)
        demo = None
        cancellation_pending = False
        can_cancel_directly = False

        if not token_doc:
            token_error = _("Peruutuslinkkiä ei tunnistettu.")
        else:
            expires_at = token_doc.get("expires_at")
            if expires_at and expires_at < datetime.utcnow():
                token_error = _("Peruutuslinkki on vanhentunut.")

            if token_doc.get("used_at"):
                token_error = _("Peruutuslinkki on jo käytetty.")

            demo = mongo.demonstrations.find_one({"_id": token_doc.get("demo_id")})
            if not demo:
                token_error = _("Mielenosoitusta ei löytynyt.")
            else:
                cancellation_pending = bool(demo.get("cancellation_requested"))
                can_cancel_directly = bool(token_doc.get("official_contact"))

                if request.method == "POST" and not token_error:
                    reason = (request.form.get("reason") or "").strip() or None

                    try:
                        if can_cancel_directly:
                            cancel_demo(
                                demo,
                                cancelled_by={
                                    "email": token_doc.get("organizer_email"),
                                    "source": "organizer_link",
                                    "official_contact": True,
                                },
                                reason=reason,
                            )
                            flash_message(_("Mielenosoitus on merkitty perutuksi."), "success")
                        else:
                            request_cancellation_case(
                                demo,
                                reason=reason,
                                requester_email=token_doc.get("organizer_email"),
                                official_contact=False,
                                source="organizer_link",
                            )
                            flash_message(_("Peruutuspyyntö on lähetetty ylläpidolle."), "info")

                        mark_token_used(token_doc.get("_id"), reason or "submitted")
                        return redirect(url_for("demonstration_detail", demo_id=token_doc.get("demo_id")))
                    except Exception:
                        logger.exception("Failed to handle cancellation from token")
                        flash_message(_("Peruutusta ei voitu käsitellä."), "error")

        if not demo:
            demo = {
                "title": _("Mielenosoitus"),
                "date": "",
                "city": "",
                "cancelled": False,
            }

        demo_date = ""
        try:
            date_value = demo.get("date")
            if isinstance(date_value, datetime):
                demo_date = date_value.strftime("%d.%m.%Y")
            elif date_value:
                demo_date = datetime.fromisoformat(date_value).strftime("%d.%m.%Y")
        except (TypeError, ValueError):
            demo_date = date_value or ""

        return render_template(
            "cancel_demonstration.html",
            demo=demo,
            demo_date=demo_date,
            token_error=token_error,
            cancellation_pending=cancellation_pending,
            can_cancel_directly=can_cancel_directly,
        )

    def fetch_geocode_data(demo):
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
        
    from math import ceil
    from datetime import datetime
    from bson import ObjectId

    @app.route("/demonstration/<parent>/children", methods=["GET"])
    def siblings_meeting(parent):
        parent_demo = RecurringDemonstration.from_id(parent)

        
        # Fetch precomputed stats
        stats = mongo.recu_stats.find_one({"parent": ObjectId(parent)}) or {}
        total_count = stats.get("total_count", 0)
        future_count = stats.get("future_count", 0)
        past_count = stats.get("past_count", 0)

        return render_template(
            "siblings.html",
            parent_demo=parent_demo,
            total_count=total_count,
            future_count=future_count,
            past_count=past_count,
            parent_id=parent
        )

    @app.route("/ohjeet/")
    @app.route("/ohjeet")
    @login_required
    @admin_required
    def public_guides():
        return render_template("ohjeet/index.html")

                
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


    DEMOS_PER_PAGE = 6  # adjust how many demos per page

    @app.route("/organization/<org_id>")
    def org(org_id):
        _org = mongo.organizations.find_one({"_id": ObjectId(org_id)})
        if _org is None:
            flash_message("Organisaatiota ei löytynyt.", "error")
            return redirect(url_for("index"))
        
        _org = Organization.from_dict(_org)
        
        if not _org.verified:
            _org.fill_url = url_for("fill", org_id=org_id)
       
        return render_template(
            "organizations/details.html",
            org=_org,
            org_id=str(org_id)
        )
        
    @app.route("/organization/<org_id>/save_suggestion", methods=["POST"])
    def save_suggestion(org_id):
        _org = mongo.organizations.find_one({"_id": ObjectId(org_id)})
        if _org is None:
            flash_message("Organisaatiota ei löytynyt.", "error")
            return redirect(url_for("index"))

        suggestion = {
            "organization_id": ObjectId(org_id),
            "timestamp": datetime.utcnow(),
            "created_at": datetime.utcnow(),
            "fields": {},
            "meta": {
                "ip": request.remote_addr,
                "user_agent": request.headers.get("User-Agent"),
                "submitter_email": request.form.get("email")
            },
            "status": {
                "state": "pending",
                "updated_at": datetime.utcnow(),
                "updated_by": None,
                "notes": None
            },
            "audit_log": [
                {
                    "action": "created",
                    "timestamp": datetime.utcnow(),
                    "user": None
                }
            ]
        }


        # Normal fields
        for field in ["name", "description", "website", "email"]:
            val = request.form.get(field)
            if val and val.strip():
                suggestion["fields"][field] = val.strip()

        # Socials
        platforms = request.form.getlist("social_platform[]")
        urls = request.form.getlist("social_url[]")
        socials = {}
        for platform, url in zip(platforms, urls):
            if platform.strip() and url.strip():
                socials[platform.strip()] = url.strip()
        if socials:
            suggestion["fields"]["social_media_links"] = socials

        # Save to DB
        result = mongo.org_edit_suggestions.insert_one(suggestion)
        suggestion_id = str(result.inserted_id)
        
        
        Case.create_new(
            case_type="organization_edit_suggestion",
            suggestion=suggestion,
            submitter_id=current_user._id if current_user else None, # or ObjectId of submitter doc if you want
            meta={"urgency": "high"}  # optional, can be extended
        )

        # --- 💌 Email notifications ---
        review_link = url_for(
            "admin_org.review_suggestion",
            org_id=org_id,
            suggestion_id=suggestion_id,
            _external=True
        )

        ctx_admin = {
            "org_name": _org.get("name"),
            "org_id": str(org_id),
            "fields": suggestion["fields"],
            "review_link": review_link,
            "submitted_at": suggestion["timestamp"].strftime("%Y-%m-%d %H:%M UTC"),
            "ip": suggestion["meta"]["ip"],
            "user_agent": suggestion["meta"]["user_agent"],
        }

        email_sender.queue_email(
            template_name="admin_org_suggestion_notification.html",
            subject=f"Uusi organisaatiotietojen muokkauspyyntö: {_org.get('name')}",
            recipients=["tuki@mielenosoitukset.fi"],
            context=ctx_admin,
        )

      

        flash_message("Kiitos! Ehdotuksesi on tallennettu ja se tarkistetaan pian 💖", "success")
        return redirect(url_for("org", org_id=org_id))

        
    @app.route("/organization/<org_id>/fill")
    def fill(org_id):
        _org = mongo.organizations.find_one({"_id": ObjectId(org_id)})
        if _org is None:
            flash_message("Organisaatiota ei löytynyt.", "error")
            return redirect(url_for("index"))
        
        _org = Organization.from_dict(_org)
       
        return render_template(
            "organizations/fill_info.html",
            organization=_org,
            org_id=str(org_id)
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

    from flask import jsonify, get_flashed_messages, current_app
    import warnings

    @app.route("/get_flash_messages", methods=["GET"])
    def get_flash_message_messages():
        warnings.warn(
            "The /get_flash_messages endpoint is deprecated and will be removed in the next major release. "
            "Use embedded flash messages in API responses instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        messages = get_flashed_messages(with_categories=True)
        if not messages:
            return jsonify(messages=[])

        flash_message_data = [
            {"category": category, "message": message} for category, message in messages
        ]
        return jsonify(messages=flash_message_data)

    
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
    

    @app.context_processor
    def inject_user_notifications():
        """
        Makes `user_notifications` available in all templates.

        Shape per item:
        id, type, message, icon, link, time, created_at, read
        """
        if not current_user.is_authenticated:
            return {"user_notifications": []}

        try:
            raw = fetch_notifications(current_user.id, limit=20)
            serialized = [serialize_notification(n) for n in raw]
            return {"user_notifications": serialized}
        except Exception:
            # Avoid breaking templates if Mongo is down
            return {"user_notifications": []}

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
    @cache.cached(timeout=300)  # cache for 5 minutes
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
        
        noindex_nofollow = False

        
        if month == 0 and year == 0:
            month = today.month
            year = today.year
            return redirect(url_for("calendar_month_view", year=year, month=month))
        
        if year < 2000 or year > 2100:
            noindex_nofollow = True
            
            
            
        if year is None or month is None:
            year, month = today.year, today.month

        # Haetaan kaikki demonstraatiot
        demonstrations = list(demonstrations_collection.find(DEMO_FILTER))

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
        
        old_view = request.cookies.get("old-calendar-view") == "true"

        
        template_name = "demo_views/calendar_grid_old.html" if old_view else "demo_views/calendar_grid.html"
        
        return render_template(
            template_name,
            year=year,
            month=month,
            month_name=month_names[month],
            month_days=month_days,
            month_demos=month_demos,
            prev_year=prev_year,
            prev_month=prev_month,
            next_year=next_year,
            next_month=next_month,
            noindex_nofollow=noindex_nofollow
        )

    # ============================
    # Year view
    # ============================
    @app.route("/calendar/<int:year>/")
    def calendar_year_view(year):
        # Haetaan kaikki demonstraatiot
        demonstrations = list(demonstrations_collection.find(DEMO_FILTER))

        noindex_nofollow = False
        if year < 2000 or year > 2100:
            noindex_nofollow = True
            
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
            year_demos=year_demos,
            noindex_nofollow=noindex_nofollow
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
    from flask import Response

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

    @app.route("/pride-nakyvaksi")
    def pride_nakyvaksi():
        return render_template("pride-nakyvaksi/index.html")

    
    @app.route("/upcoming/translations/")
    def upcoming_translations():
        return render_template("upcoming/translations.html")
    
    @app.before_request
    def _check_panic_mode():
        if not request.path.startswith("/admin") and not request.path.startswith("/users/auth") and not request.path.startswith("/static"):
            if PANIC_MODE:
                return render_template("heavy.html")
