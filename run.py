import os
from app import create_app

app = create_app()


def main():
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
