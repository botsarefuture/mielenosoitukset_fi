"""Compatibility wrapper around the shared DatabaseManager package.

The project previously shipped its own `DatabaseManager` implementation. To align
with the maintained upstream library while keeping existing imports stable, this
module proxies to ``botsarefuture/DatabaseManager`` and injects the app's
``Config`` so configuration continues to come from the project's settings file.
"""

from DatabaseManager import DatabaseManager as UpstreamDatabaseManager
from config import Config

__all__ = ["DatabaseManager"]


def _get_manager():
    """Return the shared upstream DatabaseManager configured with the app Config."""

    return UpstreamDatabaseManager.get_instance(config_class=Config())


class DatabaseManager:
    """Thin proxy that preserves the legacy API against the upstream manager."""

    def __init__(self):
        self._manager = _get_manager()

    @classmethod
    def get_instance(cls):
        return _get_manager()

    def get_db(self, db_name=None):
        return self._manager.get_db(db_name)

    def close_connection(self):
        return self._manager.close_connection()

    @staticmethod
    def legacy_get_db():
        return _get_manager().get_db()

    def __getattr__(self, name):
        return getattr(self._manager, name)
