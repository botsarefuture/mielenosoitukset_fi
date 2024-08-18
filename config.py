import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_secret_key'
    MONGO_URI = os.environ.get('MONGO_URI') or 'mongodb://95.216.148.93:27017/mielenosoitukset'
    MAIL_SERVER = 'mail3.luova.club'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'verso@mielenterveyskaikille.fi' # Set in environment or config file
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'Shohp8sa!'  # Set in environment or config file
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'verso@mielenterveyskaikille.fi'
