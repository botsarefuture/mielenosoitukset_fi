"""
DatabaseManager Module
======================

This module provides a singleton class `DatabaseManager` to manage MongoDB connections.
It ensures thread-safe initialization and provides methods to retrieve and close database connections.

Classes
-------
DatabaseManager
    Singleton class to manage MongoDB connections.

Examples
--------
>>> from mielenosoitukset_fi.database_manager import DatabaseManager
>>> db_manager = DatabaseManager.get_instance()
>>> db = db_manager.get_db("mydatabase")
>>> collection = db["mycollection"]
>>> collection.find_one({"name": "example"})
"""

from mielenosoitukset_fi.utils.logger import logger
from pymongo import MongoClient, errors
from threading import Lock
from config import Config  # Import the Config class


class DatabaseManager:
    """
    Singleton class to manage MongoDB connections.

    .. versionchanged:: 1.1.0
        Updated field names to use underscores and added docstrings in numpydoc format.
    """

    _instance = None  # Singleton instance
    _lock = Lock()  # Ensure thread-safe initialization

    def __init__(self):
        """
        Initializes the DatabaseManager singleton with MongoDB connection settings.

        .. versionchanged:: 1.1.0
            Updated field names to use underscores and added docstrings in numpydoc format.
        """
        if DatabaseManager._instance is None:
            with DatabaseManager._lock:
                if DatabaseManager._instance is None:
                    logger.info("Initializing DatabaseManager instance.")
                    self._config = Config()
                    self._mongo_uri = (
                        self._config.MONGO_URI or "mongodb://localhost:27017"
                    )
                    self._default_db_name = self._config.MONGO_DBNAME or "testdb"
                    self._client = None
                    logger.warning(self._config)

                    self._databases = {}  # Cache for database instances
                    self._initialized = False
                    DatabaseManager._instance = self
        else:
            logger.warning("DatabaseManager instance already exists. Returning it.")

    def _init_client(self):
        """
        Initialize the MongoDB client with connection pooling and timeout options.

        .. versionchanged:: 1.1.0
            Updated field names to use underscores and added docstrings in numpydoc format.
        """
        if self._initialized:
            return

        if not self._mongo_uri:
            logger.error("Missing MongoDB configuration: 'MONGO_URI'.")
            raise RuntimeError("Database configuration is missing 'MONGO_URI'.")

        try:
            self._client = MongoClient(
                self._mongo_uri,
                serverSelectionTimeoutMS=5000,
                maxPoolSize=50,
                minPoolSize=5,
            )
            self._client.admin.command("ping")  # Verify connection
            self._initialized = True
            logger.info(f"Connected to MongoDB at {self._mongo_uri}")
        except errors.ServerSelectionTimeoutError as e:
            logger.error(f"MongoDB connection timeout: {e}")
            raise RuntimeError(f"Failed to connect to MongoDB: {e}")
        except Exception as e:
            logger.error(f"MongoDB connection error: {e}")
            raise RuntimeError(f"Failed to connect to MongoDB: {e}")

    def get_db(self, db_name=None):
        """
        Retrieve a MongoDB database object, using cached connections where possible.

        Parameters
        ----------
        db_name : str, optional
            The name of the database to connect to. If None, the default database name is used.

        Returns
        -------
        Database
            The MongoDB database object.

        Examples
        --------
        >>> db_manager = DatabaseManager.get_instance()
        >>> db = db_manager.get_db("mydatabase")
        >>> collection = db["mycollection"]
        >>> collection.find_one({"name": "example"})

        .. versionchanged:: 1.1.0
            Updated field names to use underscores and added docstrings in numpydoc format.
        """
        if self._client is None:
            logger.info("MongoDB client not initialized. Initializing now.")
            self._init_client()

        db_name = db_name or self._default_db_name
        if db_name in self._databases:
            logger.info(f"Using cached connection for database: {db_name}")
            return self._databases[db_name]

        logger.info(f"Connecting to new database: {db_name}")
        db = self._client[db_name]
        self._databases[db_name] = db
        return db

    def close_connection(self):
        """
        Close the MongoDB client connection gracefully.

        Examples
        --------
        >>> db_manager = DatabaseManager.get_instance()
        >>> db_manager.close_connection()

        .. versionchanged:: 1.1.0
            Updated field names to use underscores and added docstrings in numpydoc format.
        """
        if self._client:
            self._client.close()
            logger.info("MongoDB connection closed.")
        else:
            logger.warning("No active MongoDB connection to close.")

    @classmethod
    def get_instance(cls):
        """
        Provide the singleton instance of DatabaseManager.

        Returns
        -------
        DatabaseManager
            The singleton instance of DatabaseManager.

        Examples
        --------
        >>> db_manager = DatabaseManager.get_instance()
        >>> db = db_manager.get_db()

        .. versionchanged:: 1.1.0
            Updated field names to use underscores and added docstrings in numpydoc format.
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

        Returns
        -------
        Database
            The MongoDB database object.

        Examples
        --------
        >>> db = DatabaseManager.legacy_get_db()
        >>> collection = db["mycollection"]
        >>> collection.find_one({"name": "example"})

        .. versionchanged:: 1.1.0
            Updated field names to use underscores and added docstrings in numpydoc format.
        """
        return DatabaseManager.get_instance().get_db()
