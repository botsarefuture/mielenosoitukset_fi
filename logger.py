# logger.py

import logging
from logging.handlers import RotatingFileHandler

def setup_logger():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Create log file handler
    file_handler = RotatingFileHandler('app.log', maxBytes=10000000, backupCount=3)
    file_handler.setLevel(logging.INFO)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)

    # Create formatter and add it to handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# Initialize logger
logger = setup_logger()
