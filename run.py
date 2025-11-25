import os
import sys
from mielenosoitukset_fi.app import create_app
from mielenosoitukset_fi.scripts.send_demo_reminders import send_reminders_scheduled as send_reminders

from mielenosoitukset_fi.utils.aggregate_analytics import rollup_events

import threading

try:
    app = create_app()
except web-1          | INFO:config:Loading configuration from config.yaml...Exception as e:
    print(f"Error creating app: {e}")
    sys.exit(1)
def run_rollup_in_thread():
    
    # if dev environment variable is set, do not run rollup in thread
    if os.getenv("FLASK_ENV") == "development":
        app.logger.info("Skipping rollup_events in development environment")
        return None

    def target():
        try:
            with app.app_context():
                rollup_events()
        except Exception as e:
            app.logger.error(f"Error in rollup_events thread: {e}")

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    return thread


def main():
    """
    The main entry point for the application.

    This function retrieves configuration settings for the application,
    updates the application's configuration to set the default language
    to Finnish, and then runs the application.

    Configuration settings:
    - PORT: The port number on which the application will run. Defaults to 5000 if not set.
    - DEBUG: The debug mode for the application. Defaults to False if not set.

    The application's configuration is updated to set the default locale to Finnish
    and to support only the Finnish language.

    The application is then started with the specified debug mode and port number.
    """
    if len(sys.argv) > 1 and sys.argv[1] == "demo_sche":
        # Usage: python3 run.py demo_sche test@example.com
        override_email = sys.argv[2] if len(sys.argv) > 2 else None
        send_reminders(override_email=override_email, force_all=True)
        return

    # Retrieve configurations with fallback defaults
    port = int(os.getenv("PORT", app.config.get("PORT", 5000)))
    host = os.getenv("HOST", app.config.get("HOST", "0.0.0.0"))
    debug = os.getenv("DEBUG", str(app.config.get("DEBUG", False))).lower() in (
        "true",
        "1",
        "t",
    )

    # Modify the current configuration
    app.config.update(
        BABEL={
            "DEFAULT_LOCALE": "fi",
            "SUPPORTED_LOCALES": ["fi"],
            "LANGUAGES": {"fi": "Suomi"},
        }
    )  # Change the default language to Finnish
    
    run_rollup_in_thread()

    app.run(debug=debug, host=host, port=port)


if __name__ == "__main__":

    from mielenosoitukset_fi.utils.logger import logger
    logger.info("Starting application...")
    try:
        main()
    except Exception as e:
        logger.error(f"Application died with exception: {e}")
    finally:
        # DIE WITH A ERROR CODE
        sys.exit(1)

    logger.info("Application died.")
