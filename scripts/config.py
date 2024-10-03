import os
import yaml


class Config:
    # Load configuration from YAML file
    with open("config.yaml", "r") as file:
        config = yaml.safe_load(file)

    SECRET_KEY = config.get("SECRET_KEY") or "secret_key"
    MONGO_URI = config.get("MONGO_URI")
    MONGO_DBNAME = config.get("MONGO_DBNAME")
    MAIL_SERVER = config.get("MAIL_SERVER")
    MAIL_PORT = config.get("MAIL_PORT") or 587
    MAIL_USE_TLS = config.get("MAIL_USE_TLS", True)
    MAIL_USERNAME = config.get("MAIL_USERNAME")
    MAIL_PASSWORD = config.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = config.get("MAIL_DEFAULT_SENDER") or MAIL_USERNAME
    PORT = config.get("PORT")
    DEBUG = config.get("DEBUG")
    # SERVER_NAME = config.get('SERVER_NAME') or 'www.mielenosoitukset.fi'
    # PREFERRED_URL_SCHEME = config.get('PREFERRED_URL_SCHEME') or 'https'

    # TODO: Ensure sensitive data such as 'SECRET_KEY', 'MAIL_PASSWORD', and 'MONGO_URI' are secured properly.
    # TODO: Use a more secure method to manage and rotate secrets, such as a secrets manager or environment variable manager.
    # TODO: Validate configuration values at runtime to ensure they meet expected formats and constraints (e.g., check if `MAIL_PORT` is a valid port number).
    # TODO: Consider setting up logging to capture configuration loading errors for easier debugging.
    # TODO: Review and update the default values to be more secure or more appropriate for your environment if used in production.
