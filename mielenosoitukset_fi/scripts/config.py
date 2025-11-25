import os
import yaml
import logging
from typing import Any, Dict


class Config:
    """Configuration class to load and manage application settings."""

    # Configure logging for configuration loading
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    def load_yaml(file_path: str) -> Dict[str, Any]:
        """Load configuration from a YAML file.

        Parameters
        ----------
        file_path :
            str:
        file_path : str :

        file_path : str :

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
    MONGO_URI = os.getenv("MONGO_URI", config.get("MONGO_URI", ""))
    MONGO_DBNAME = os.getenv("MONGO_DBNAME", config.get("MONGO_DBNAME", "default_db"))

    # Mail Configuration
    MAIL_CONFIG = config.get("MAIL", {})
    MAIL_SERVER = MAIL_CONFIG.get("SERVER", "localhost")
    MAIL_PORT = MAIL_CONFIG.get("PORT", 587)
    MAIL_USE_TLS = MAIL_CONFIG.get("USE_TLS", True)
    MAIL_USERNAME = MAIL_CONFIG.get("USERNAME", "")
    MAIL_PASSWORD = MAIL_CONFIG.get("PASSWORD", "")
    MAIL_DEFAULT_SENDER = MAIL_CONFIG.get("DEFAULT_SENDER", MAIL_USERNAME)

    # Flask Configuration
    SECRET_KEY = config.get("SECRET_KEY", "secret_key")
    PORT = config.get("PORT", 8000)
    DEBUG = config.get("DEBUG", False)

    # S3 Configuration
    S3_CONFIG = config.get("S3", {})
    ACCESS_KEY = S3_CONFIG.get("ACCESS_KEY")
    SECRET_KEY = S3_CONFIG.get("SECRET_KEY")
    ENDPOINT_URL = S3_CONFIG.get("ENDPOINT_URI")

    @classmethod
    def init_config(cls) -> None:
        """Initialize configuration and log validation messages."""
        if not cls.MONGO_URI:
            cls.logger.warning("MONGO_URI is not set.")
        if not cls.MAIL_USERNAME or not cls.MAIL_PASSWORD:
            cls.logger.warning("Mail credentials are not set.")
        if cls.SECRET_KEY == "secret_key":
            cls.logger.warning("Default SECRET_KEY should be changed for security.")


# Initialize the configuration
Config.init_config()

