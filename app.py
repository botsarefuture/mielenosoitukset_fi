from flask import Flask, request, session, g
from flask_babel import Babel
from flask_login import LoginManager
from bson.objectid import ObjectId
from apscheduler.schedulers.background import BackgroundScheduler

from utils.logger import logger
from database_manager import DatabaseManager
from users.models import User, AnonymousUser
from error_handlers import register_error_handlers

from scripts.repeat_v2 import main as repeat_main
from scripts.update_demo_organizers import main as update_main
from scripts.in_past import hide_past

from utils import VERSION

import os

# if env var forcerun
if os.environ.get("FORCERUN"): # Set this via: export FORCERUN=1
    repeat_main()
    update_main()
    hide_past()
    exit()
    

# Create and configure the scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(repeat_main, "interval", hours=24)  # Run every 24 hours
scheduler.add_job(update_main, "interval", hours=1)  # Run every hour

# Initialize Babel
babel = Babel()

def create_app() -> Flask:
    """Create and configure the Flask application."""
    
    app = Flask(__name__)
    app.config.from_object("config.Config")  # Load configurations from 'config.Config'

    # Locale selector function
    def get_locale():
        return session.get("locale", request.accept_languages.best_match(app.config["BABEL_SUPPORTED_LOCALES"], app.config["BABEL_DEFAULT_LOCALE"])) # Get locale from session or request headers or else use default locale

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
    login_manager.login_view = "users.auth.login"  # Redirect to login view if not authenticated
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
    from admin import admin_bp, admin_user_bp, admin_demo_bp, admin_org_bp, admin_recu_demo_bp
    from users import _BLUEPRINT_ as user_bp
    from api import api_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(admin_demo_bp)
    app.register_blueprint(admin_recu_demo_bp)
    app.register_blueprint(admin_user_bp)
    app.register_blueprint(admin_org_bp)
    app.register_blueprint(user_bp, url_prefix="/users/")
    app.register_blueprint(api_bp, url_prefix="/api/")

    # Import and initialize routes
    import basic_routes
    basic_routes.init_routes(app)

    logger.info("Flask application created successfully.")

    if app.debug:
        @app.route("/ping")
        def ping():
            return f"Pong from {VERSION}"
        
    @app.context_processor
    def utility_processor():
        def get_org_name(org_id):
            return mongo.organizations.find_one({"_id": ObjectId(org_id)}).get("name")
        
        def get_supported_locales():
            return app.config["BABEL_SUPPORTED_LOCALES"]
        
        def get_lang_name(lang_code):
            return app.config["BABEL_LANGUAGES"].get(lang_code)
        
        return dict(get_org_name=get_org_name, get_supported_locales=get_supported_locales, get_lang_name=get_lang_name)
    
    with app.app_context():
        scheduler.add_job(hide_past, "interval", hours=24)  # Run every 24 hours
        scheduler.start()
        
    return app
