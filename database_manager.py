import json
from pymongo import MongoClient

class DatabaseManager:
    def __init__(self):
        self.client = None
        self.db = None
        self.load_config()
        self.init_db()

    def load_config(self):
        """Load database configuration from db_config.json."""
        with open('db_config.json') as config_file:
            self.config = json.load(config_file)
    
    def init_db(self):
        """Initialize MongoDB connection using the loaded configuration."""
        mongo_uri = self.config.get("MONGO_URI")
        db_name = self.config.get("MONGO_DBNAME")
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]

    def get_db(self):
        """Get the MongoDB database."""
        return self.db
