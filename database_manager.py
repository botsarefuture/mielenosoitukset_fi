import json
from pymongo import MongoClient
import os

class DatabaseManager:
    def __init__(self):
        self.client = None
        self.db = None
        self.config = None
        self.load_config()
        self.init_db()

    def load_config(self):
        """
        Load database configuration from db_config.json or environment variables.
        """
        try:
            # Prefer environment variables if they exist for sensitive data
            mongo_uri = os.getenv('MONGO_URI')
            mongo_dbname = os.getenv('MONGO_DBNAME')

            if mongo_uri and mongo_dbname:
                self.config = {
                    "MONGO_URI": mongo_uri,
                    "MONGO_DBNAME": mongo_dbname
                }
            else:
                with open('db_config.json') as config_file:
                    self.config = json.load(config_file)
        except FileNotFoundError:
            raise RuntimeError("Configuration file 'db_config.json' not found and no environment variables set.")
        except json.JSONDecodeError:
            raise RuntimeError("Configuration file 'db_config.json' is not a valid JSON.")
    
    def init_db(self):
        """
        Initialize MongoDB connection using the loaded configuration.
        """
        mongo_uri = self.config.get("MONGO_URI")
        db_name = self.config.get("MONGO_DBNAME")

        if not mongo_uri or not db_name:
            raise RuntimeError("Database configuration is missing 'MONGO_URI' or 'MONGO_DBNAME'.")

        try:
            self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            # Attempt to connect to trigger potential network errors
            self.client.admin.command('ping')
            self.db = self.client[db_name]
        except Exception as e:
            raise RuntimeError(f"Failed to connect to MongoDB: {str(e)}")

    def get_db(self):
        """
        Get the MongoDB database.
        """
        if self.db is None:
            raise RuntimeError("Database has not been initialized.")
        return self.db