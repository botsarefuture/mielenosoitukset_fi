from flask_babel import Babel, gettext
from utils.logger import logger

from flask import Flask, request
from flask_login import LoginManager
from bson.objectid import ObjectId
from apscheduler.schedulers.background import BackgroundScheduler

from database_manager import DatabaseManager
from auth.models import User, AnonymousUser
from error_handlers import register_error_handlers
from scripts.repeat_v2 import main as repeat_main
from scripts.update_demo_organizers import main as update_main
from utils import VERSION

# Create and configure the scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(repeat_main, "interval", hours=24)  # Run every 24 hours
scheduler.add_job(update_main, "interval", hours=1)  # Run every hour
scheduler.start()

# Initialize Babel
babel = Babel()


def create_app() -> Flask:
    """Create and configure the Flask application.
    
    Returns:
        Flask:
            The configured Flask application instance.
        
    Initializes:
    ------------
    - Flask application with configurations from 'config.Config'.
    - Babel for internationalization with default locale 'fi' and supported locales 'en', 'fi', 'sv'.
    - MongoDB connection using DatabaseManager.
    - Flask-Login for user session management.
    - Registers error handlers.
    - Registers blueprints for admin, auth, user, and API routes.
    - Initializes basic routes.
    - Adds a '/ping' route for debugging if app is in debug mode.
    - Adds a context processor to fetch organization name by ID.
    
    User Loader:
    ------------
    - Loads a user from the database by user_id for Flask-Login.
    
    Context Processor:
    ------------------
    - Provides a utility function to get organization name from organization ID.
    
    Changelog:
    ----------
    v2.6.0:
    - Updated the docstring.
    - Moved the babel config to the config file.
    
    v2.5.0:
    - Added a context processor to get the organization name from the organization ID.
    
    v2.4.0:
    - Refined code
    - Logging level now reflects the app.debug variable
    - Introduced /ping route for debugging purposes
    """
    
    app = Flask(__name__)
    app.config.from_object("config.Config") # Load configurations from 'config.Config'

    # Locale selector function
    def get_locale():
        # TODO: #196 Modify this function to check user settings in the database
        
        return request.accept_languages.best_match(
            app.config["BABEL_SUPPORTED_LOCALES"]
        )

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
        "auth.login"  # Redirect to login view if not authenticated
    )

    login_manager.anonymous_user = AnonymousUser

    # User Loader function
    @login_manager.user_loader
    def load_user(user_id):
        """
        Load a user from the database by user_id.
        """
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
    )

    app.register_blueprint(admin_bp)
    app.register_blueprint(admin_demo_bp)
    app.register_blueprint(admin_recu_demo_bp)
    app.register_blueprint(admin_user_bp)
    app.register_blueprint(admin_org_bp)

    from auth import auth_bp

    app.register_blueprint(auth_bp, url_prefix="/auth/")

    from user import user_bp

    app.register_blueprint(user_bp)

    from api import api_bp

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
        return dict(get_org_name=get_org_name)

    return app
