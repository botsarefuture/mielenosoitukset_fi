import logging
from pymongo import MongoClient, errors
from threading import Lock
from config import Config  # Import the Config class

__name__ = "Database Manager"

# Setup logging
logger = logging.getLogger(__name__)


class DatabaseManager:
    _instance = None  # Singleton instance
    _lock = Lock()  # Ensure thread-safe initialization

    def __init__(self):
        """Initializes the DatabaseManager singleton with MongoDB connection settings."""
        if DatabaseManager._instance is None:
            with DatabaseManager._lock:
                if DatabaseManager._instance is None:
                    logger.info("Initializing DatabaseManager instance.")
                    self.config = Config()
                    self.mongo_uri = (
                        self.config.MONGO_URI or "mongodb://localhost:27017"
                    )
                    self.default_db_name = self.config.MONGO_DBNAME or "testdb"
                    self.client = None
                    self._databases = {}  # Cache for database instances
                    self._initialized = False
                    DatabaseManager._instance = self
        else:
            logger.warning("DatabaseManager instance already exists. Returning it.")

    def _init_client(self):
        """Initialize the MongoDB client with connection pooling and timeout options."""
        if self._initialized:
            return

        if not self.mongo_uri:
            logger.error("Missing MongoDB configuration: 'MONGO_URI'.")
            raise RuntimeError("Database configuration is missing 'MONGO_URI'.")

        try:
            self.client = MongoClient(
                self.mongo_uri,
                serverSelectionTimeoutMS=5000,
                maxPoolSize=50,
                minPoolSize=5,
            )
            self.client.admin.command("ping")  # Verify connection
            self._initialized = True
            logger.info(f"Connected to MongoDB at {self.mongo_uri}")
        except errors.ServerSelectionTimeoutError as e:
            logger.error(f"MongoDB connection timeout: {e}")
            raise RuntimeError(f"Failed to connect to MongoDB: {e}")
        except Exception as e:
            logger.error(f"MongoDB connection error: {e}")
            raise RuntimeError(f"Failed to connect to MongoDB: {e}")

    def get_db(self, db_name=None):
        """Retrieve a MongoDB database object, using cached connections where possible."""
        if self.client is None:
            logger.info("MongoDB client not initialized. Initializing now.")
            self._init_client()

        db_name = db_name or self.default_db_name
        if db_name in self._databases:
            logger.info(f"Using cached connection for database: {db_name}")
            return self._databases[db_name]

        logger.info(f"Connecting to new database: {db_name}")
        db = self.client[db_name]
        self._databases[db_name] = db
        return db

    def close_connection(self):
        """Close the MongoDB client connection gracefully."""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed.")
        else:
            logger.warning("No active MongoDB connection to close.")

    @classmethod
    def get_instance(cls):
        """Provide the singleton instance of DatabaseManager."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = DatabaseManager()
        return cls._instance

    @staticmethod
    def legacy_get_db():
        """Backward-compatible method for retrieving the default database."""
        return DatabaseManager.get_instance().get_db()
