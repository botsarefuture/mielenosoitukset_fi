from datetime import datetime, date, time
import time as process_time
from flask import Flask, redirect, request, session, g, url_for
from flask_babel import Babel
from flask_login import LoginManager
from bson.objectid import ObjectId
from mielenosoitukset_fi.background_jobs import JOB_DEFINITIONS, init_background_jobs

from mielenosoitukset_fi.utils.logger import logger
from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.users.models import User, AnonymousUser
from mielenosoitukset_fi.error_handlers import register_error_handlers
from mielenosoitukset_fi.utils.media_helpers import (
    get_demo_cover_image,
    get_demo_gallery_images,
)

import sys
import os
from zoneinfo import ZoneInfo


from mielenosoitukset_fi.utils import VERSION

from werkzeug.middleware.proxy_fix import ProxyFix

from mielenosoitukset_fi.kampanja import campaign_bp
from mielenosoitukset_fi.notifications_bp import notif_bp

import os

from mielenosoitukset_fi.utils.wrappers import depracated_endpoint

from flask_caching import Cache  # Added for caching

# Initialize Babel

babel = Babel()


from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def _configure_timezone(app):
    """Ensure process-level timezone matches Finland (or configured value)."""
    tz_name = app.config.get("DEFAULT_TIMEZONE") or "Europe/Helsinki"
    os.environ["TZ"] = tz_name
    try:
        process_time.tzset()
    except AttributeError:
        logger.warning("tzset() not available on this platform; system timezone unchanged.")

    try:
        app.config["LOCAL_TIMEZONE"] = ZoneInfo(tz_name)
    except Exception:
        logger.exception("Failed to load timezone %s, falling back to UTC.", tz_name)
        app.config["LOCAL_TIMEZONE"] = ZoneInfo("UTC")


def create_app() -> Flask:
    """Create and configure the Flask application."""

    app = Flask(__name__)
    app.config.from_object("config.Config")  # Load configurations from 'config.Config'
    _configure_timezone(app)
    
    Limiter(
        get_remote_address,
        app=app,
        default_limits=["86400 per day", "3600 per hour", "10 per second"],
        storage_uri=app.config['MONGO_URI'],
    )
    
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1) # Fix for reverse proxy
        # Initialize Flask-Caching
        
    from mielenosoitukset_fi.utils.cache import cache, skip_cache_public_only
    cache.init_app(app)
    

    # Locale selector function
    def get_locale():
        return session.get(
            "locale",
            request.accept_languages.best_match(
                app.config["BABEL_SUPPORTED_LOCALES"],
                app.config["BABEL_DEFAULT_LOCALE"],
            ),
        )  # Get locale from session or request headers or else use default locale

    # Initialize Babel
    babel.init_app(app, locale_selector=get_locale)

    logger.info("Creating Flask application...")

    # Register error handlers
    register_error_handlers(app)

    # Initialize MongoDB
    db_manager = DatabaseManager().get_instance()
    mongo = db_manager.get_db()

    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = (
        "users.auth.login"  # Redirect to login view if not authenticated
    )
    
    login_manager.anonymous_user = AnonymousUser

    # User Loader function
    @login_manager.user_loader
    def load_user(user_id):
        user_doc = mongo.users.find_one({"_id": ObjectId(user_id)})
        if user_doc:
            logger.info(f"User loaded: {user_doc.get('username')}")
            return User.from_db(user_doc)
        logger.warning(f"User not found with id: {user_id}")
        return None

    # Import and register blueprints
    from admin import (
        admin_bp,
        admin_user_bp,
        admin_demo_bp,
        admin_case_bp,
        admin_demo_api_bp,
        admin_org_bp,
        admin_recu_demo_bp,
        admin_media_bp,
        board_bp,
        audit_bp,
        admin_kampanja_bp
    )
    from users import _BLUEPRINT_ as user_bp
    from users import chat_ws
    from flask_socketio import SocketIO, emit, join_room
    from api import api_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(admin_demo_bp)
    app.register_blueprint(admin_demo_api_bp, url_prefix="/api/admin/demo/")
    
    app.register_blueprint(admin_recu_demo_bp)
    app.register_blueprint(admin_user_bp)
    app.register_blueprint(admin_org_bp)
    app.register_blueprint(admin_media_bp)
    app.register_blueprint(admin_kampanja_bp)
    app.register_blueprint(admin_case_bp)
    #app.register_blueprint(admin_case_bp)
    
    app.register_blueprint(user_bp, url_prefix="/users/")
    app.register_blueprint(api_bp, url_prefix="/api/")
    
    
    app.register_blueprint(campaign_bp)
    app.register_blueprint(notif_bp)
    from flask_babel import format_timedelta, get_locale
    def timeago(dt):
        from datetime import datetime
        return format_timedelta(datetime.utcnow() - dt,
                                locale=str(get_locale()),
                                granularity='minute')
    app.jinja_env.filters["timeago"] = timeago
    app.register_blueprint(board_bp)
    
    socketio = SocketIO(app, cors_allowed_origins="*", message_queue="redis://localhost:6379/mosoitukset_fi")
    app.register_blueprint(chat_ws.chat_ws)
    chat_ws.init_socketio(socketio)
    app.register_blueprint(audit_bp)

    # Import and initialize routes
    import basic_routes

    basic_routes.init_routes(app)

    logger.info("Flask application created successfully.")

    # pylint: disable=unused-function
    @app.template_filter("date")
    def date_filter(value, format_):
        """
        Format a date object into a string.

        Parameters
        ----------
        value : datetime.date or datetime.datetime
            The date object to format.
        format_ : str, optional
            The format string (default is '%Y-%m-%d').

        Returns
        -------
        
        str
            The formatted date string.
        """
        try:
            # We want the output to be in the format_, the input is iso 8601
            va = datetime.fromisoformat(value)
            return va.strftime(format_)
        except Exception:
            return value

    # utils/jinja_filters.py (or similar)
    @app.template_filter('datetimeformat')
    def datetimeformat(value, fmt="%d.%m.%Y %H:%M"):
        if isinstance(value, (datetime,)):
            return value.strftime(fmt)
        return value  # fallback

        
    

    @app.template_filter("time")
    def time_filter(value, format_='%H:%M'):
        """
        Format a time object into a string.

        Parameters
        ----------
        value : datetime.date, datetime.datetime, datetime.time or str
            The date/time object to format.
        format_ : str, optional
            The format string (default is '%H:%M').

        Returns
        -------
        str
            The formatted date string.
        """
        try:
            # If the value is a string, try to convert it to a time object
            if isinstance(value, str):
                # Try to parse the string into a time object
                value = datetime.strptime(value, '%H:%M:%S').time()

            if isinstance(value, time):  # Check if value is a time object
                return value.strftime(format_)
            elif isinstance(value, datetime):  # If it's a datetime object
                return value.time().strftime(format_)
            elif isinstance(value, date):  # If it's a date object
                return value.strftime(format_)
            else:
                return value  # If it's not a recognized type, return as-is
        except Exception as e:
            return f"Error formatting time: {e}"




    
    if app.debug:

        @app.route("/ping")
        @cache.cached(timeout=30, unless=skip_cache_public_only)  # Cache the response for 30 seconds
        def ping():
            return f"Pong from {VERSION}"
        
    @app.route("/screenshot/<demo_id>")
    @depracated_endpoint
    def screenshot(demo_id):
        # check if the screenshot is already created
        from mielenosoitukset_fi.utils import _CUR_DIR
        base_path = os.path.join(_CUR_DIR, "static/demo_preview")
        _path = os.path.normpath(os.path.join(base_path, f"{demo_id}.png"))
        if not _path.startswith(base_path):
            raise Exception("Invalid path")
        if os.path.exists(_path):
            return redirect(f"/static/demo_preview/{demo_id}.png")
        
        from mielenosoitukset_fi.utils.screenshot import create_screenshot
        from mielenosoitukset_fi.utils.classes.Demonstration import Demonstration
        data = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
        if data and data.get("preview_image"):
            return redirect(data.get("preview_image"))
        demo = Demonstration.from_dict(data)
        screenshot_path = create_screenshot(demo)
        if screenshot_path is None:
            return redirect(url_for("static", filename="img/e.png"))
        return redirect(url_for("static", filename=screenshot_path.replace("static/", "").replace("//", "/")))
    
    from datetime import datetime, timedelta
    from bson import ObjectId

    @app.context_processor
    def utility_processor():
        def get_admin_tasks():
            tasks = []

            # --- DEMONSTRATION approval tasks ---
            waiting_demos = list(
                mongo.demonstrations.find({
                    "approved": False,
                    "hide": False,
                    "$or": [
                        {"rejected": False},
                        {"rejected": {"$exists": False}}
                    ]
                }).sort("created_at", -1)
            )
            for demo in waiting_demos:
                tasks.append({
                    "type": "demo",
                    "id": str(demo["_id"]),
                    "title": demo.get("title", "Nimetön mielenosoitus"),
                    "created_at": demo.get("created_datetime", datetime.now()) or datetime.now(),
                    "status": "waiting_approval",
                    "link": url_for("admin_demo.edit_demo", demo_id=demo["_id"]),
                })

            # --- ORG SUGGESTIONS tasks ---
            org_suggestions = list(
                mongo.org_edit_suggestions.find({
        "status.state": {"$nin": ["partially_applied", "applied", "rejected", "cancelled"]}
        }).sort("created_at", -1)
            )
            for s in org_suggestions:
                org = mongo.organizations.find_one({"_id": ObjectId(s["organization_id"])})
                org_name = org["name"] if org else "Tuntematon organisaatio"
                tasks.append({
                    "type": "org_suggestion",
                    "id": str(s["_id"]),
                    "title": f"Organisaation päivitysehdotus: {org_name}",
                    "created_at": s.get("created_at", datetime.now()),
                    "status": (s.get("status") or {}).get("state"),
                    "link": url_for("admin_org.review_suggestion", org_id=s["organization_id"], suggestion_id=s["_id"]),
                })

            # sort by creation time descending
            tasks.sort(key=lambda x: x.get("created_at", datetime.min), reverse=True)

            return tasks


        def get_org_name(org_id):
            org = mongo.organizations.find_one({"_id": ObjectId(org_id)}, {"name": 1})
            return org.get("name") if org else "Tuntematon"

        def _get_user_by_id(user_id, fields=None, include_none=False):
            if fields is None:
                fields = ["username", "display_name", "profile_picture", "last_login"]

            try:
                oid = ObjectId(user_id) if not isinstance(user_id, ObjectId) else user_id
            except Exception:
                return None

            user = mongo.users.find_one({"_id": oid})
            if not user:
                return None

            user_data = {}
            for field in fields:
                if field in user:
                    if user[field] is not None or include_none:
                        user_data[field] = user[field]

            return user_data

        def get_supported_locales():
            return app.config["BABEL_SUPPORTED_LOCALES"]

        def get_lang_name(lang_code):
            return app.config["BABEL_LANGUAGES"].get(lang_code)

        def get_default_locale():
            return app.config["BABEL_DEFAULT_LOCALE"]

        # Get all tasks
        tasks = get_admin_tasks()
        tasks_amount_total = len(tasks)

        # Demonstrations done
        tasks_amount_done = sum(1 for t in tasks if t.get("approved", False) or t.get("state") == "applied")

        return dict(
            get_org_name=get_org_name,
            get_supported_locales=get_supported_locales,
            get_lang_name=get_lang_name,
            get_default_locale=get_default_locale,
            tasks=tasks,
            tasks_amount_total=tasks_amount_total,
            tasks_amount_done=tasks_amount_done,
            _get_user_by_id=_get_user_by_id
        )



    
    # if env var forcerun
    if os.environ.get("FORCERUN") or (
        len(sys.argv) > 1 and sys.argv[1] == "force"
    ):  # Set this via: export FORCERUN=1
        # To unset: unset FORCERUN
        
        # Usage: python3 run.py force [task1,task2,...]
        available_tasks = {job.key: job.func for job in JOB_DEFINITIONS}

        def run_selected_tasks(selected, till_param=None):
            """Run selected maintenance tasks.

            Parameters
            ----------
            selected : list of str
                List of task names to run.
            till_param : int | None
                Optional number of days to limit run_preview task.
            """
            with app.app_context():
                for task_name in selected:
                    if task_name == "run_preview":
                        # Ask for force
                        i = input("Run force update? (y/n): ").lower()
                        force_flag = i == "y"

                        # Ask for till (optional)
                        if till_param is None:
                            j = input("Limit previews to how many days? (0 = all): ").strip()
                            try:
                                till = int(j)
                            except ValueError:
                                till = 0
                        else:
                            till = till_param

                        available_tasks[task_name](force=force_flag, till=till)
                    elif task_name in available_tasks:
                        available_tasks[task_name]()
                    else:
                        app.logger.warning(f"Unknown task: {task_name}. Available tasks: {list(available_tasks.keys())}")

        if len(sys.argv) > 2:
            # User specified tasks as comma-separated list
            tasks = [t.strip() for t in sys.argv[2].split(",")]
            run_selected_tasks(tasks)
        else:
            # Run all tasks
            run_selected_tasks(list(available_tasks.keys()))
        exit()

    # Initialize background jobs (scheduler + logging)
    init_background_jobs(app)
        
    @app.template_filter('displayname_or_username')
    def displayname_or_username(user):
        return user.displayname or user.username
    
    def attr_or_get(obj, *attrs):
        for a in attrs:
            # try attribute first
            if hasattr(obj, a) and getattr(obj, a):
                return getattr(obj, a)
            # fallback for dicts
            if isinstance(obj, dict) and a in obj and obj[a]:
                return obj[a]
        return None
    
    app.jinja_env.globals.update(
        attr_or_get=attr_or_get,
        get_demo_cover_image=get_demo_cover_image,
        get_demo_gallery_images=get_demo_gallery_images,
    )

    return app
