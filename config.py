import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_secret_key'
    MONGO_URI = os.environ.get('MONGO_URI') or 'mongodb://95.216.148.93:27017/mielenosoitukset'
    MAIL_SERVER = 'mail3.luova.club'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'verso@mielenterveyskaikille.fi'  # Set in environment or config file
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'Shohp8sa!'  # Set in environment or config file
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'verso@mielenterveyskaikille.fi'
    #SERVER_NAME = 'www.mielenosoitukset.fi'
    #PREFERRED_URL_SCHEME = 'https'
    
    # TODO: Ensure sensitive data such as 'SECRET_KEY', 'MAIL_PASSWORD', and 'MONGO_URI' are secured properly.
    # TODO: Use a more secure method to manage and rotate secrets, such as a secrets manager or environment variable manager.
    # TODO: Validate configuration values at runtime to ensure they meet expected formats and constraints (e.g., check if `MAIL_PORT` is a valid port number).
    # TODO: Consider setting up logging to capture configuration loading errors for easier debugging.
    # TODO: Review and update the default values to be more secure or more appropriate for your environment if used in production.
