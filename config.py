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
        cls.BABEL_DEFAULT_LOCALE = cls.BABEL_CONFIG.get("DEFAULT_LOCALE", "fi")
        cls.BABEL_SUPPORTED_LOCALES = cls.BABEL_CONFIG.get(
            "SUPPORTED_LOCALES",
            ["fi", "en"],
        )
        cls.BABEL_PUBLIC_LOCALES = cls.BABEL_CONFIG.get(
            "PUBLIC_LOCALES",
            [cls.BABEL_DEFAULT_LOCALE],
        )
        cls.BABEL_LANGUAGES = cls.BABEL_CONFIG.get(
            "LANGUAGES",
            {"fi": "Suomi", "en": "English"},
        )
        cls.DEEPL_API_KEY = config.get("DEEPL_API_KEY", "")
        cls.DEEPL_API_URL = config.get(
            "DEEPL_API_URL",
            "https://api-free.deepl.com/v2/translate",
        )
        # Free geocoding API used to resolve demonstration address coordinates.
        # Keep the legacy key as the default so existing deployments keep
        # working until they add their own GEOCODE_API_KEY to config.
        cls.GEOCODE_API_KEY = config.get(
            "GEOCODE_API_KEY",
            "66df12ce96495339674278ivnc82595",
        )
        cls.UI_TRANSLATION_SYNC_ENABLED = config.get("UI_TRANSLATION_SYNC_ENABLED", False)
        cls.UI_TRANSLATION_SYNC_REPO_PATH = config.get("UI_TRANSLATION_SYNC_REPO_PATH", "")
        cls.UI_TRANSLATION_SYNC_BASE_BRANCH = config.get("UI_TRANSLATION_SYNC_BASE_BRANCH", "main")
        cls.UI_TRANSLATION_SYNC_BRANCH_PREFIX = config.get(
            "UI_TRANSLATION_SYNC_BRANCH_PREFIX",
            "ui-translation",
        )
        cls.UI_TRANSLATION_SYNC_REMOTE = config.get("UI_TRANSLATION_SYNC_REMOTE", "origin")
        cls.UI_TRANSLATION_SYNC_GIT_AUTHOR_NAME = config.get(
            "UI_TRANSLATION_SYNC_GIT_AUTHOR_NAME",
            "Mielenosoitukset UI Translation Bot",
        )
        cls.UI_TRANSLATION_SYNC_GIT_AUTHOR_EMAIL = config.get(
            "UI_TRANSLATION_SYNC_GIT_AUTHOR_EMAIL",
            "translations@mielenosoitukset.fi",
        )
        cls.UI_TRANSLATION_GITHUB_REPO = config.get("UI_TRANSLATION_GITHUB_REPO", "")
        cls.UI_TRANSLATION_GITHUB_TOKEN = config.get("UI_TRANSLATION_GITHUB_TOKEN", "")
        cls.UI_TRANSLATION_GITHUB_API_URL = config.get(
            "UI_TRANSLATION_GITHUB_API_URL",
            "https://api.github.com",
        )
        cls.UI_TRANSLATION_GITHUB_AUTO_MERGE = config.get(
            "UI_TRANSLATION_GITHUB_AUTO_MERGE",
            False,
        )
        cls.UI_TRANSLATION_GITHUB_MERGE_METHOD = config.get(
            "UI_TRANSLATION_GITHUB_MERGE_METHOD",
            "squash",
        )

        cls.SECRET_KEY = config.get("SECRET_KEY", "secret_key")
        cls.PORT = config.get("PORT", 8000)
        cls.DEBUG = config.get("DEBUG", True)

        cls.S3_CONFIG = config.get("S3", {})
        cls.ACCESS_KEY = cls.S3_CONFIG.get("ACCESS_KEY")
        cls.S3_SECRET_KEY = cls.S3_CONFIG.get("SECRET_KEY")
        cls.ENDPOINT_URL = cls.S3_CONFIG.get("ENDPOINT_URI")
        cls.S3_BUCKET = cls.S3_CONFIG.get("BUCKET", "mielenosoitukset.fi")
        cls.CDN_BASE_URL = config.get(
            "CDN_BASE_URL",
            "https://cdn2.mielenosoitukset.fi",
        )

        cls.ENABLE_CHAT = config.get("ENABLE_CHAT", True)

        # ---- WebAuthn / passkeys --------------------------------------------
        # The relying-party identity must match how browsers see the origin.
        # In development `localhost` is a valid secure context; production and
        # staging deployments must configure the real RP ID and origin(s).
        cls.WEBAUTHN_RP_ID = config.get("WEBAUTHN_RP_ID", "localhost")
        cls.WEBAUTHN_RP_NAME = config.get("WEBAUTHN_RP_NAME", "Mielenosoitukset.fi")
        cls.WEBAUTHN_ORIGIN = config.get("WEBAUTHN_ORIGIN", "http://localhost:8000")
        allowed_origins = config.get("WEBAUTHN_ALLOWED_ORIGINS")
        cls.WEBAUTHN_ALLOWED_ORIGINS = (
            allowed_origins if isinstance(allowed_origins, list) and allowed_origins
            else [cls.WEBAUTHN_ORIGIN]
        )
        # How long a step-up ("sudo") elevation stays valid before the user
        # must authenticate again for a sensitive operation.
        cls.SUDO_DEFAULT_TIMEOUT = int(config.get("SUDO_DEFAULT_TIMEOUT", 900))

        # ---- Session ----------------------------------------------------------
        # Target normal authenticated session lifetime (~12 hours). Sessions are
        # marked permanent on login so this value is actually applied.
        cls.PERMANENT_SESSION_LIFETIME = config.get(
            "PERMANENT_SESSION_LIFETIME", 12 * 60 * 60
        )
        cls.SESSION_COOKIE_HTTPONLY = config.get("SESSION_COOKIE_HTTPONLY", True)
        cls.SESSION_COOKIE_SAMESITE = config.get("SESSION_COOKIE_SAMESITE", "Lax")
        cls.SESSION_COOKIE_SECURE = config.get("SESSION_COOKIE_SECURE", False)

        cls.ALLOWED_EXTENSIONS = cls.S3_CONFIG.get(
            "ALLOWED_EXTENSIONS",
            {"png", "jpg", "jpeg", "gif"},
        )
        cls.UPLOADS_FOLDER = cls.S3_CONFIG.get("UPLOADS_FOLDER", "uploads")
        cls.ENFORCE_RATELIMIT = config.get("ENFORCE_RATELIMIT", True)

        cls.ADMIN_EMAIL = config.get("ADMIN_EMAIL", "itc@luova.club")
        cls.ADMIN_MCP = config.get("ADMIN_MCP", {})

        cls.CACHE_TYPE = config.get("CACHE_TYPE", "SimpleCache")
        cls.CACHE_DEFAULT_TIMEOUT = config.get("CACHE_DEFAULT_TIMEOUT", 300)
        cls.CACHE_REDIS_HOST = config.get("REDIS_HOST", "localhost")
        cls.CACHE_REDIS_PORT = config.get("REDIS_PORT", 6379)
        cls.CACHE_REDIS_DB = config.get("REDIS_DB", 0)
        cls.DEFAULT_TIMEZONE = config.get("DEFAULT_TIMEZONE", "Europe/Helsinki")
        cls.TESTING = config.get("TESTING", False)
        cls.ENABLE_EMAIL_WORKER = config.get("ENABLE_EMAIL_WORKER", True)

        # Support ticket ingress (IMAP polling of the tuki@ mailbox)
        cls.TICKET_INGRESS_ENABLED = config.get("TICKET_INGRESS_ENABLED", False)
        cls.TICKET_IMAP_SERVER = config.get("TICKET_IMAP_SERVER", "mail.luova.club")
        cls.TICKET_IMAP_PORT = config.get("TICKET_IMAP_PORT", 993)
        cls.TICKET_IMAP_USE_SSL = config.get("TICKET_IMAP_USE_SSL", True)
        cls.TICKET_IMAP_USERNAME = config.get("TICKET_IMAP_USERNAME", "")
        cls.TICKET_IMAP_PASSWORD = config.get("TICKET_IMAP_PASSWORD", "")
        cls.TICKET_IMAP_MAILBOX = config.get("TICKET_IMAP_MAILBOX", "INBOX")
        # YAML often represents intentionally omitted optional values as null.
        # Treat null/empty SMTP overrides as absent instead of replacing the
        # working IMAP-host defaults with unusable connection settings.
        cls.TICKET_SMTP_SERVER = (
            config.get("TICKET_SMTP_SERVER") or cls.TICKET_IMAP_SERVER
        )
        cls.TICKET_SMTP_PORT = config.get("TICKET_SMTP_PORT") or 587
        ticket_smtp_tls = config.get("TICKET_SMTP_USE_TLS")
        cls.TICKET_SMTP_USE_TLS = (
            True if ticket_smtp_tls is None else bool(ticket_smtp_tls)
        )
        cls.TICKET_ESCALATION_EMAIL = config.get(
            "TICKET_ESCALATION_EMAIL",
            "olivia@mielenosoitukset.fi",
        )
        cls.TICKET_SLA_HOURS = config.get("TICKET_SLA_HOURS", 48)
        cls.TICKET_SENDER = config.get(
            "TICKET_SENDER",
            cls.MAIL_DEFAULT_SENDER,
        )
        cls.TICKET_URGENT_KEYWORD = config.get("TICKET_URGENT_KEYWORD", "URGENT")
        cls.TICKET_POLL_SECONDS = config.get("TICKET_POLL_SECONDS", 120)
        cls.TICKET_IGNORED_SENDERS = config.get("TICKET_IGNORED_SENDERS", []) or []
        cls.CITY_ASSIGNMENT_ESCALATION_HOURS = config.get(
            "CITY_ASSIGNMENT_ESCALATION_HOURS", 24
        )
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

        # ---- Built-in first-party analytics ---------------------------------
        # Server-side pageview counting without cookies or JavaScript. Set to
        # false to stop recording (dashboards keep working on existing data).
        cls.SITE_ANALYTICS_ENABLED = bool(config.get("SITE_ANALYTICS_ENABLED", True))

        # ---- Matomo (optional, client-side) ----------------------------------
        # The legacy client-side Matomo tracker in base.html can be turned off
        # now that built-in analytics cover basic pageviews. It is enabled by
        # default so current deployments keep reporting until it is switched.
        cls.MATOMO_ENABLED = bool(config.get("MATOMO_ENABLED", True))

        # ---- Facebook event import (Apify) -------------------------------------
        # Used by the submission form's "fetch event details from Facebook"
        # helper. The token is read from the YAML config (or environment, see
        # the example configs) and must not be hardcoded in the repository.
        cls.APIFY_API_BASE_URL = config.get(
            "APIFY_API_BASE_URL",
            "https://api.apify.com/v2",
        )
        cls.APIFY_API_TOKEN = config.get("APIFY_API_TOKEN", "")
        cls.APIFY_FACEBOOK_ACTOR_ID = config.get(
            "APIFY_FACEBOOK_ACTOR_ID",
            "apify~facebook-events-scraper",
        )
        cls.APIFY_SYNC_TIMEOUT_SECONDS = int(
            config.get("APIFY_SYNC_TIMEOUT_SECONDS", 120)
        )

    @classmethod
    def reload(cls, path="config.yaml") -> None:
        """Reload configuration from the active config file."""
        cls._apply_config(cls.load_yaml(path))
    
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
Config.reload(os.environ.get("CONFIG_YAML_PATH", "config.yaml"))
Config.init_config()  # This will log warnings if essential configuration variables are not set or use default values.
