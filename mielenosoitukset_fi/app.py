from datetime import datetime
from flask import Flask, redirect, request, session, g, url_for
from flask_babel import Babel
from flask_login import LoginManager
from bson.objectid import ObjectId
from apscheduler.schedulers.background import BackgroundScheduler

from mielenosoitukset_fi.utils.logger import logger
from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.users.models import User, AnonymousUser
from mielenosoitukset_fi.error_handlers import register_error_handlers

from mielenosoitukset_fi.scripts.repeat_v2 import main as repeat_main
from mielenosoitukset_fi.scripts.update_demo_organizers import main as update_main
from mielenosoitukset_fi.scripts.in_past import hide_past
from mielenosoitukset_fi.scripts.CL import main as cl_main
from mielenosoitukset_fi.scripts.preview_image_creator import run as run_preview

from mielenosoitukset_fi.utils.analytics import prep
import sys
import os
from mielenosoitukset_fi.AM import am_bp

from flask_autosec import FlaskAutoSec

from mielenosoitukset_fi.utils import VERSION

from werkzeug.middleware.proxy_fix import ProxyFix

import os

from mielenosoitukset_fi.utils.wrappers import depracated_endpoint

from flask_caching import Cache  # Added for caching

# Initialize Babel
babel = Babel()


from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def create_app() -> Flask:
    """Create and configure the Flask application."""

    app = Flask(__name__)
    app.config.from_object("config.Config")  # Load configurations from 'config.Config'
    try:
        security = FlaskAutoSec(app.config.get("ENFORCE_RATELIMIT", True))
        security.init_app(app)
    except Exception as e:
        Limiter(
            get_remote_address,
            app=app,
            default_limits=["86400 per day", "3600 per hour", "10 per second"],
            storage_uri=f"{app.config['MONGO_URI']}/mielenosoitukset_fi.limiter",
        )
        logger.error(f"Error initializing FlaskAutoSec: {e}")
        logger.info("Using Flask-Limiter instead.")
    
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1) # Fix for reverse proxy

    # Initialize Flask-Caching
    cache = Cache(app)
        

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
        admin_org_bp,
        admin_recu_demo_bp,
        admin_media_bp,
    )
    from users import _BLUEPRINT_ as user_bp
    from api import api_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(admin_demo_bp)
    app.register_blueprint(admin_recu_demo_bp)
    app.register_blueprint(admin_user_bp)
    app.register_blueprint(admin_org_bp)
    app.register_blueprint(admin_media_bp)
    app.register_blueprint(user_bp, url_prefix="/users/")
    app.register_blueprint(api_bp, url_prefix="/api/")
    app.register_blueprint(am_bp.am_bp, url_prefix="/am/")

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

    from datetime import datetime, date, time
    from datetime import datetime, date, time

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
        @cache.cached(timeout=30)  # Cache the response for 30 seconds
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
        demo = Demonstration.from_dict(data)
        screenshot_path = create_screenshot(demo)
        print(screenshot_path)
        if screenshot_path is None:
            return redirect(url_for("static", filename="img/e.png"))
        return redirect(url_for("static", filename=screenshot_path.replace("static/", "").replace("//", "/")))
    
    

    @app.context_processor
    def utility_processor():
        def get_admin_tasks():
            # check if any demonstrations are waiting for approval
            waiting = list(mongo.demonstrations.find({"approved": False, "hide": False}))
            print(waiting)
            
            return waiting
            
        def get_org_name(org_id):
            return mongo.organizations.find_one({"_id": ObjectId(org_id)}).get("name")

        def get_supported_locales():
            return app.config["BABEL_SUPPORTED_LOCALES"]

        def get_lang_name(lang_code):
            return app.config["BABEL_LANGUAGES"].get(lang_code)

        return dict(
            get_org_name=get_org_name,
            get_supported_locales=get_supported_locales,
            get_lang_name=get_lang_name,
            tasks=get_admin_tasks(),
        )

    
    # if env var forcerun
    if os.environ.get("FORCERUN") or (
        len(sys.argv) == 2 and sys.argv[1] == "force"
    ):  # Set this via: export FORCERUN=1
        # To unset: unset FORCERUN
        

        with app.app_context():
            cl_main()
            repeat_main()
            update_main()
            hide_past()
            prep()
            run_preview()
        exit()

    # Create and configure the scheduler
    scheduler = BackgroundScheduler()
    with app.app_context():
        scheduler.add_job(repeat_main, "interval", hours=24)  # Run every 24 hours
        scheduler.add_job(update_main, "interval", hours=1)  # Run every hour
        scheduler.add_job(cl_main, "interval", hours=24)  # Run every 24 hours
        scheduler.add_job(prep, "interval", minutes=15)
        scheduler.add_job(run_preview, "interval", hours=24)  # Run every 24 hours

        
    with app.app_context():
        scheduler.add_job(hide_past, "interval", hours=24)  # Run every 24 hours
        scheduler.start()

    return app
