import yaml
from typing import Any, Dict
import logging


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

    # Load the configuration
    config = load_yaml("config.yaml")

    # MongoDB Configuration
    MONGO_URI = config.get("MONGO_URI", "")
    MONGO_DBNAME = config.get("MONGO_DBNAME", "default_db")

    # Mail Configuration
    MAIL_CONFIG = config.get("MAIL", {})
    MAIL_SERVER = MAIL_CONFIG.get("SERVER", "localhost")
    MAIL_PORT = MAIL_CONFIG.get("PORT", 587)
    MAIL_USE_TLS = MAIL_CONFIG.get("USE_TLS", True)
    MAIL_USERNAME = MAIL_CONFIG.get("USERNAME", "")
    MAIL_PASSWORD = MAIL_CONFIG.get("PASSWORD", "")
    MAIL_DEFAULT_SENDER = MAIL_CONFIG.get("DEFAULT_SENDER", MAIL_USERNAME)

    # Babel Configuration
    BABEL_CONFIG = config.get("BABEL", {})
    BABEL_DEFAULT_LOCALE = BABEL_CONFIG.get("DEFAULT_LOCALE", "en")
    BABEL_SUPPORTED_LOCALES = BABEL_CONFIG.get("SUPPORTED_LOCALES", ["en"])
    BABEL_LANGUAGES = BABEL_CONFIG.get("LANGUAGES", {"en": "English"})

    # Flask Configuration
    SECRET_KEY = config.get("SECRET_KEY", "secret_key")
    PORT = config.get("PORT", 8000)
    DEBUG = config.get("DEBUG", True)

    # S3 Configuration
    S3_CONFIG = config.get("S3", {})
    ACCESS_KEY = S3_CONFIG.get("ACCESS_KEY")
    SECRET_KEY = S3_CONFIG.get("SECRET_KEY")
    ENDPOINT_URL = S3_CONFIG.get("ENDPOINT_URI")
    # Canonical bucket and CDN host
    S3_BUCKET = S3_CONFIG.get("BUCKET", "mielenosoitukset.fi")
    CDN_HOST = S3_CONFIG.get("CDN_HOST", "https://cdn2.mielenosoitukset.fi")

    # Allowed file extensions for uploads
    ALLOWED_EXTENSIONS = S3_CONFIG.get(
        "ALLOWED_EXTENSIONS", {"png", "jpg", "jpeg", "gif"}
    )
    UPLOADS_FOLDER = S3_CONFIG.get("UPLOADS_FOLDER", "uploads")

    ENFORCE_RATELIMIT = config.get("ENFORCE_RATELIMIT", True)  # Enable rate limiting

    # Admin stuff
    ADMIN_EMAIL = config.get("ADMIN_EMAIL", "itc@luova.club")  # Admin email address

    # Redis / Cache Configuration
    CACHE_TYPE = config.get("CACHE_TYPE", "SimpleCache")
    CACHE_DEFAULT_TIMEOUT = config.get("CACHE_DEFAULT_TIMEOUT", 300)
    CACHE_REDIS_HOST = config.get("REDIS_HOST", "localhost")
    CACHE_REDIS_PORT = config.get("REDIS_PORT", 6379)
    CACHE_REDIS_DB = config.get("REDIS_DB", 0)
    
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
Config.init_config()  # This will log warnings if essential configuration variables are not set or use default values.
