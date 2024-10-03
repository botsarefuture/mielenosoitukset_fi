from flask import Flask
from flask_login import LoginManager
from bson.objectid import ObjectId
from database_manager import DatabaseManager
from auth.models import User  # Import User model
from emailer.EmailSender import EmailSender
from error import register_error_handlers

from apscheduler.schedulers.background import BackgroundScheduler

from scripts.repeat_v2 import main as repeat_main
from scripts.update_demo_organizers import main as update_main

# Create and configure the scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(repeat_main, 'interval', hours=24)  # Run every 60 seconds
scheduler.add_job(update_main, 'interval', hours=1)
scheduler.start()

def create_app():
    # Initialize EmailSender
    email_sender = EmailSender()

    app = Flask(__name__)
    app.config.from_object("config.Config")

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

    # User Loader function
    @login_manager.user_loader
    def load_user(user_id):
        """
        Load a user from the database by user_id.
        """
        user_doc = mongo.users.find_one({"_id": ObjectId(user_id)})
        if user_doc:
            return User.from_db(user_doc)
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

    return app
