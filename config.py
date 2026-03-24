import logging
import os
from typing import Any, Dict

import yaml


class Config:
    """Configuration class to load and manage application settings.

    Attributes:
        config (dict): Loaded configuration from the YAML file.
        MONGO_URI (str): MongoDB URI.
        MONGO_DBNAME (str): MongoDB database name.
        MAIL_CONFIG (dict): Mail configuration settings.
        MAIL_SERVER (str): Mail server address.
        MAIL_PORT (int): Mail server port.
        MAIL_USE_TLS (bool): Use TLS for mail server.
        MAIL_USERNAME (str): Mail server username.
        MAIL_PASSWORD (str): Mail server password.
        MAIL_DEFAULT_SENDER (str): Default sender email address.
        SECRET_KEY (str): Secret key for Flask application.
        PORT (int): Port number for the Flask application.
        DEBUG (bool): Debug mode for the Flask application.
        S3_CONFIG (dict): S3 configuration settings.
        ACCESS_KEY (str): S3 access key.
        SECRET_KEY (str): S3 secret key.
        ENDPOINT_URL (str): S3 endpoint URL.
        ADMIN_EMAIL (str): Admin email address.

    Methods:
    --------
        load_yaml(file_path: str) -> Dict[str, Any]:
            Load configuration from a YAML file.
        init_config() -> None:
            Initialize configuration and log validation messages.

    Changelog:
    ----------
    v2.6.0:
    - Moved babel configuration to the config file.
    - Added a method to initialize the configuration and log validation messages.
    - Updated the docstring.

    Parameters
    ----------

    Returns
    -------


    """

    # Configure logging for configuration loading
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    @classmethod
    def _config_path(cls) -> str:
        """Return the active configuration file path."""
        return os.environ.get("CONFIG_YAML_PATH", "config.yaml")

    @staticmethod
    def load_yaml(file_path: str) -> Dict[str, Any]:
        """Load configuration from a YAML file.

        Parameters
        ----------
        file_path: str :


        Returns
        -------

        """

        try:
            with open(file_path, "r") as file:
                config = yaml.safe_load(file) or {}
                logging.info(f"Loaded configuration from {file_path}")
                return config
        except Exception as e:
            logging.error(f"Failed to load configuration from {file_path}: {e}")
            return {}

    @classmethod
    def _apply_config(cls, config: Dict[str, Any]) -> None:
        """Apply loaded config values to the class attributes."""
        cls.config = config

        cls.MONGO_URI = config.get("MONGO_URI", "")
        cls.MONGO_DBNAME = config.get("MONGO_DBNAME", "default_db")

        cls.MAIL_CONFIG = config.get("MAIL", {})
        cls.MAIL_SERVER = cls.MAIL_CONFIG.get("SERVER", "localhost")
        cls.MAIL_PORT = cls.MAIL_CONFIG.get("PORT", 587)
        cls.MAIL_USE_TLS = cls.MAIL_CONFIG.get("USE_TLS", True)
        cls.MAIL_USERNAME = cls.MAIL_CONFIG.get("USERNAME", "")
        cls.MAIL_PASSWORD = cls.MAIL_CONFIG.get("PASSWORD", "")
        cls.MAIL_DEFAULT_SENDER = cls.MAIL_CONFIG.get(
            "DEFAULT_SENDER",
            cls.MAIL_USERNAME,
        )

        cls.BABEL_CONFIG = config.get("BABEL", {})
        cls.BABEL_DEFAULT_LOCALE = cls.BABEL_CONFIG.get("DEFAULT_LOCALE", "en")
        cls.BABEL_SUPPORTED_LOCALES = cls.BABEL_CONFIG.get(
            "SUPPORTED_LOCALES",
            ["en"],
        )
        cls.BABEL_LANGUAGES = cls.BABEL_CONFIG.get("LANGUAGES", {"en": "English"})

        cls.SECRET_KEY = config.get("SECRET_KEY", "secret_key")
        cls.PORT = config.get("PORT", 8000)
        cls.DEBUG = config.get("DEBUG", True)

        cls.S3_CONFIG = config.get("S3", {})
        cls.ACCESS_KEY = cls.S3_CONFIG.get("ACCESS_KEY")
        cls.SECRET_KEY = cls.S3_CONFIG.get("SECRET_KEY")
        cls.ENDPOINT_URL = cls.S3_CONFIG.get("ENDPOINT_URI")
        cls.S3_BUCKET = cls.S3_CONFIG.get("BUCKET", "mielenosoitukset.fi")
        cls.CDN_BASE_URL = config.get(
            "CDN_BASE_URL",
            "https://cdn2.mielenosoitukset.fi",
        )

        cls.ENABLE_CHAT = config.get("ENABLE_CHAT", True)
        cls.ALLOWED_EXTENSIONS = cls.S3_CONFIG.get(
            "ALLOWED_EXTENSIONS",
            {"png", "jpg", "jpeg", "gif"},
        )
        cls.UPLOADS_FOLDER = cls.S3_CONFIG.get("UPLOADS_FOLDER", "uploads")
        cls.ENFORCE_RATELIMIT = config.get("ENFORCE_RATELIMIT", True)

        cls.ADMIN_EMAIL = config.get("ADMIN_EMAIL", "itc@luova.club")

        cls.CACHE_TYPE = config.get("CACHE_TYPE", "SimpleCache")
        cls.CACHE_DEFAULT_TIMEOUT = config.get("CACHE_DEFAULT_TIMEOUT", 300)
        cls.CACHE_REDIS_HOST = config.get("REDIS_HOST", "localhost")
        cls.CACHE_REDIS_PORT = config.get("REDIS_PORT", 6379)
        cls.CACHE_REDIS_DB = config.get("REDIS_DB", 0)
        cls.DEFAULT_TIMEZONE = config.get("DEFAULT_TIMEZONE", "Europe/Helsinki")
        cls.TESTING = config.get("TESTING", False)
        cls.ENABLE_EMAIL_WORKER = config.get("ENABLE_EMAIL_WORKER", True)
        cls.ENABLE_PANIC_THREAD = config.get("ENABLE_PANIC_THREAD", True)
        cls.ENABLE_BACKGROUND_JOBS = config.get("ENABLE_BACKGROUND_JOBS", True)
        cls.DISABLE_BACKGROUND_JOBS = config.get(
            "DISABLE_BACKGROUND_JOBS",
            not cls.ENABLE_BACKGROUND_JOBS,
        )
        cls.SOCKETIO_MESSAGE_QUEUE = config.get(
            "SOCKETIO_MESSAGE_QUEUE",
            "redis://localhost:6379/mosoitukset_fi",
        )

    @classmethod
    def reload(cls) -> None:
        """Reload configuration from the active config file."""
        cls._apply_config(cls.load_yaml(cls._config_path()))
    
    @classmethod
    def init_config(cls) -> None:
        """Initialize configuration and log validation messages.

        This method checks for the presence of essential configuration variables
        and logs warnings if they are not set or if they use default insecure values.

        Warnings:
            - Logs a warning if `MONGO_URI` is not set.
            - Logs a warning if either `MAIL_USERNAME` or `MAIL_PASSWORD` is not set.
            - Logs a warning if `SECRET_KEY` is set to the default value "secret_key".

        Parameters
        ----------

        Returns
        -------


        """

        if not cls.MONGO_URI:
            cls.logger.warning("MONGO_URI is not set.")
        if not cls.MAIL_USERNAME or not cls.MAIL_PASSWORD:
            cls.logger.warning("Mail credentials are not set.")
        if cls.SECRET_KEY == "secret_key":
            cls.logger.warning("Default SECRET_KEY should be changed for security.")


# Initialize the configuration
Config.reload()
Config.init_config()  # This will log warnings if essential configuration variables are not set or use default values.
