import os
import sys

if sys.version_info < (3, 12):
    raise RuntimeError("Mielenosoitukset.fi requires Python 3.12 or newer.")

from mielenosoitukset_fi.app import create_app
from mielenosoitukset_fi.scripts.send_demo_reminders import send_reminders_scheduled as send_reminders

from mielenosoitukset_fi.utils.aggregate_analytics import rollup_events

import threading

app = create_app()
def run_rollup_in_thread():
    def target():
        try:
            rollup_events()
        except Exception as e:
            app.logger.error(f"Error in rollup_events thread: {e}")

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    return thread


def main():
    """
    The main entry point for the application.

    This function retrieves configuration settings and runs the application.
    Locale publication is controlled by the BABEL section in the active YAML
    configuration.

    Configuration settings:
    - PORT: The port number on which the application will run. Defaults to 5000 if not set.
    - DEBUG: The debug mode for the application. Defaults to False if not set.

    The application is then started with the specified debug mode and port number.
    """
    if len(sys.argv) > 1 and sys.argv[1] == "demo_sche":
        # Usage: python3 run.py demo_sche test@example.com
        override_email = sys.argv[2] if len(sys.argv) > 2 else None
        send_reminders(override_email=override_email, force_all=True)
        return

    # Retrieve configurations with fallback defaults
    port = int(os.getenv("PORT", app.config.get("PORT", 5000)))
    host = os.getenv("HOST", app.config.get("HOST", "127.0.0.1"))
    debug = os.getenv("DEBUG", str(app.config.get("DEBUG", False))).lower() in (
        "true",
        "1",
        "t",
    )

    run_rollup_in_thread()

    app.run(host=host, debug=debug, port=port)


if __name__ == "__main__":
    main()
