import logging
from config import Config
from logging.handlers import SMTPHandler

# Set the logging level based on the DEBUG flag in Config
log_level = logging.DEBUG if Config.DEBUG else logging.INFO

# Configure logging format
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Create a logger instance
logger = logging.getLogger("Mielenosoitukset.fi")

# Optionally, add a StreamHandler to output to the console
console_handler = logging.StreamHandler()
console_handler.setLevel(log_level)
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S"
)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Send email for critical errors in production
if not Config.DEBUG:
    email_handler = SMTPHandler(
        mailhost=(Config.MAIL_SERVER, Config.MAIL_PORT),
        fromaddr=Config.MAIL_USERNAME,
        toaddrs=[
            Config.ADMIN_EMAIL
        ],  # List of recipients (could be a list of admin emails)
        subject="Critical Error in Mielenosoitukset.fi",
        credentials=(Config.MAIL_USERNAME, Config.MAIL_PASSWORD),
        secure=(),
    )
    email_handler.setLevel(logging.CRITICAL)
    email_handler.setFormatter(formatter)  # Use the same formatter for email logs
    logger.addHandler(email_handler)

# Your application will now send emails on critical errors if not in debug mode.
