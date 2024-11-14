import logging
from logging.handlers import SMTPHandler
from config import Config

def setup_logger():
    """
    Sets up the logger for the Mielenosoitukset.fi application.

    This function configures the logging settings based on the DEBUG flag in the Config class.
    It sets the logging level, formats the log messages, and adds handlers for console output
    and email notifications for critical errors in production.

    Returns:
        logging.Logger: Configured logger instance.

    Handlers:
        - StreamHandler: Outputs log messages to the console.
        - SMTPHandler: Sends email notifications for critical errors when not in DEBUG mode.

    Logging Levels:
        - DEBUG: Detailed information, typically of interest only when diagnosing problems.
        - INFO: Confirmation that things are working as expected.
        - CRITICAL: A serious error, indicating that the program itself may be unable to continue running.

    Config:
        - Config.DEBUG (bool): Flag to determine if the application is in debug mode.
        - Config.MAIL_SERVER (str): SMTP server address for sending emails.
        - Config.MAIL_PORT (int): SMTP server port.
        - Config.MAIL_USERNAME (str): Username for the SMTP server.
        - Config.MAIL_PASSWORD (str): Password for the SMTP server.
        - Config.ADMIN_EMAIL (str): Email address to send critical error notifications.
    """
    
    # Set the logging level based on the DEBUG flag in Config
    log_level = logging.DEBUG if Config.DEBUG else logging.INFO

    # Configure logging format
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
        "%Y-%m-%d %H:%M:%S"
    )

    # Create a logger instance
    logger = logging.getLogger("Mielenosoitukset.fi")
    logger.setLevel(log_level)

    # Add a StreamHandler to output to the console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Send email for critical errors in production
    if not Config.DEBUG:
        email_handler = SMTPHandler(
            mailhost=(Config.MAIL_SERVER, Config.MAIL_PORT),
            fromaddr=Config.MAIL_USERNAME,
            toaddrs=[Config.ADMIN_EMAIL],
            subject="Critical Error in Mielenosoitukset.fi",
            credentials=(Config.MAIL_USERNAME, Config.MAIL_PASSWORD),
            secure=(),
        )
        email_handler.setLevel(logging.CRITICAL)
        email_handler.setFormatter(formatter)
        logger.addHandler(email_handler)

    return logger

# Initialize the logger
logger = setup_logger()

# Your application will now send emails on critical errors if not in debug mode.
