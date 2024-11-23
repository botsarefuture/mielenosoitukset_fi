import os
from app import create_app

app = create_app()


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
    """ """
    # Retrieve configurations with fallback defaults
    port = int(os.getenv("PORT", app.config.get("PORT", 5000)))
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

    app.run(debug=debug, port=port)


if __name__ == "__main__":
    main()
