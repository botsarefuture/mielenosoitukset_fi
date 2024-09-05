from pymongo import MongoClient
from config import Config


class DatabaseManager:
    def __init__(self):
        self.client = None
        self.db = None
        self.config = Config()
        self.init_db()

    def init_db(self):
        """
        Initialize MongoDB connection using the loaded configuration.
        """
        mongo_uri = self.config.MONGO_URI
        db_name = self.config.MONGO_DBNAME

        if not mongo_uri or not db_name:
            raise RuntimeError(
                "Database configuration is missing 'MONGO_URI' or 'MONGO_DBNAME'."
            )

        try:
            self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            # Attempt to connect to trigger potential network errors
            self.client.admin.command("ping")
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
