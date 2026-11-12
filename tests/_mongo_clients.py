"""Test-session ownership for real Mongo clients referenced by legacy handles.

Only conftest installs this factory. Production DatabaseManager is unchanged.
"""

from threading import RLock

from pymongo import MongoClient


class SessionMongoClients:
    def __init__(self, uri, client_factory=MongoClient):
        self._uri = uri
        self._factory = client_factory
        self._client = None
        self._options = None
        self._closed = False
        self._lock = RLock()

    def __call__(self, uri, **options):
        with self._lock:
            if self._closed:
                raise RuntimeError("The test Mongo client owner is closed")
            if uri != self._uri:
                raise RuntimeError("Test Mongo client refuses an unexpected endpoint")
            if self._client is not None:
                if options != self._options:
                    raise RuntimeError("Test Mongo client options changed within one session")
                return self._client
            self._client = self._factory(uri, **options)
            self._options = dict(options)
            return self._client

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            client, self._client = self._client, None
        if client is not None:
            client.close()
