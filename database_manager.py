import logging
import os
from pymongo import MongoClient, errors
from threading import Lock
from config import Config  # Import the Config class

# Setup logging
logger = logging.getLogger(__name__)

class DatabaseManager:
    _instance = None  # Singleton pattern
    _lock = Lock()  # For thread safety

    def __init__(self):
        """
        Initializes the DatabaseManager. A single MongoDB client is used, and databases can be accessed dynamically.
        """
        if DatabaseManager._instance is None:
            with DatabaseManager._lock:
                if DatabaseManager._instance is None:
                    self.config = Config()
                    logger.info("Initializing DatabaseManager instance.")
                    # Load URI and default DB name from Config class
                    self.mongo_uri = self.config.MONGO_URI or 'mongodb://localhost:27017'
                    self.default_db_name = self.config.MONGO_DBNAME or 'testdb'
                    self.client = None
                    self._databases = {}  # Cache for accessed databases
                    self._initialized = False  # Track initialization status
                    DatabaseManager._instance = self  # Save as singleton instance
        else:
            logger.warning("DatabaseManager instance already initialized. Returning existing instance.")

    def _init_client(self):
        """
        Initializes MongoDB client connection. This will be reused for accessing multiple databases.
        """
        if self._initialized:
            return

        if not self.mongo_uri:
            logger.error("Missing MongoDB configuration: 'MONGO_URI'.")
            raise RuntimeError("Database configuration is missing 'MONGO_URI'.")

        try:
            # Initialize MongoDB client with connection pooling and timeout options
            self.client = MongoClient(
                self.mongo_uri,
                serverSelectionTimeoutMS=5000,  # Connection timeout
                maxPoolSize=50,  # Connection pool size (adjust as needed)
                minPoolSize=5
            )
            # Ping the server to check the connection
            self.client.admin.command("ping")
            self._initialized = True
            logger.info(f"Connected to MongoDB at URI: {self.mongo_uri}")
        except errors.ServerSelectionTimeoutError as e:
            logger.error(f"MongoDB connection timeout: {str(e)}")
            raise RuntimeError(f"Failed to connect to MongoDB: Timeout - {str(e)}")
        except Exception as e:
            logger.error(f"MongoDB connection error: {str(e)}")
            raise RuntimeError(f"Failed to connect to MongoDB: {str(e)}")

    def get_db(self, db_name=None):
        """
        Public method to dynamically switch and get the MongoDB database object.
        Defaults to the initially configured database but allows switching.
        """
        if self.client is None:
            logger.info("Initializing MongoDB client.")
            self._init_client()

        # Default to the initially configured database if not specified
        db_name = db_name or self.default_db_name

        if db_name in self._databases:
            logger.info(f"Using cached database connection for: {db_name}")
            return self._databases[db_name]

        # Create and cache the new database connection
        logger.info(f"Switching to database: {db_name}")
        db = self.client[db_name]
        self._databases[db_name] = db  # Cache the database object for future use
        return db

    def close_connection(self):
        """
        Safely closes the MongoDB client connection, ensuring no resources are leaked.
        """
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed.")
        else:
            logger.warning("Attempted to close a non-existent MongoDB connection.")

    @classmethod
    def get_instance(cls):
        """
        Singleton pattern to ensure only one instance of DatabaseManager is used.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = DatabaseManager()
        return cls._instance

    @staticmethod
    def legacy_get_db():
        """
        Backward-compatible method for retrieving the default database.
        """
        instance = DatabaseManager.get_instance()
        return instance.get_db()