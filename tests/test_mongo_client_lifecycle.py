from concurrent.futures import ThreadPoolExecutor
import threading
import time

import pytest
from pymongo import MongoClient

from config import Config
from mielenosoitukset_fi.database_manager import DatabaseManager
from tests._mongo_clients import SessionMongoClients


def test_repeated_real_manager_resets_keep_one_client_and_legacy_handles_alive(test_settings):
    assert Config.TESTING is True
    assert Config.MONGO_DBNAME == test_settings["mongo_dbname"]
    handles = []
    client_ids = set()
    before_threads = sum(thread.name.startswith("pymongo") for thread in threading.enumerate())
    for _ in range(100):
        manager = DatabaseManager.get_instance()
        handle = manager.get_db()
        assert isinstance(handle.client, MongoClient)
        assert handle.command("ping")["ok"] == 1
        client_ids.add(id(handle.client))
        handles.append(handle)
        DatabaseManager.reset_instance()
    assert len(client_ids) == 1
    assert all(handle.command("ping")["ok"] == 1 for handle in handles)
    after_threads = sum(thread.name.startswith("pymongo") for thread in threading.enumerate())
    assert after_threads <= before_threads + 4


def test_reset_still_refreshes_database_config_without_invalidating_old_handle(monkeypatch, test_settings):
    database_name = test_settings["mongo_dbname"]
    old_manager = DatabaseManager.get_instance()
    old_handle = old_manager.get_db()
    monkeypatch.setattr(Config, "MONGO_DBNAME", database_name + "_alternate")
    DatabaseManager.reset_instance()
    new_manager = DatabaseManager.get_instance()
    new_handle = new_manager.get_db()
    assert old_manager is not new_manager
    assert old_handle.name == database_name
    assert new_handle.name == database_name + "_alternate"
    assert old_handle.client is new_handle.client
    assert old_handle.command("ping")["ok"] == new_handle.command("ping")["ok"] == 1


def test_owner_is_lazy_and_rejects_foreign_endpoint_or_changed_options():
    calls = []
    owner = SessionMongoClients("mongodb://fixture.test", lambda *a, **k: calls.append((a, k)) or object())
    assert not calls
    with pytest.raises(RuntimeError, match="unexpected endpoint"):
        owner("mongodb://not-the-test-endpoint")
    assert not calls
    client = owner("mongodb://fixture.test", maxPoolSize=50)
    assert owner("mongodb://fixture.test", maxPoolSize=50) is client
    with pytest.raises(RuntimeError, match="options changed"):
        owner("mongodb://fixture.test", maxPoolSize=1)
    assert len(calls) == 1


def test_owner_constructs_one_client_under_concurrent_requests():
    barrier = threading.Barrier(4)
    constructed = []

    def factory(*args, **kwargs):
        time.sleep(.02)  # expose overlapping construction if the owner lock regresses
        client = object()
        constructed.append(client)
        return client

    owner = SessionMongoClients("mongodb://fixture.test", factory)

    def obtain():
        barrier.wait(timeout=5)
        return owner("mongodb://fixture.test")

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(obtain) for _ in range(4)]
        clients = [future.result(timeout=5) for future in futures]
    assert len(constructed) == 1
    assert all(client is constructed[0] for client in clients)


def test_owner_closes_once_and_cannot_reopen_after_session_end():
    class Client:
        closes = 0

        def close(self):
            self.closes += 1

    client = Client()
    owner = SessionMongoClients("mongodb://fixture.test", lambda *a, **k: client)
    assert owner("mongodb://fixture.test") is client
    owner.close()
    owner.close()
    assert client.closes == 1
    with pytest.raises(RuntimeError, match="closed"):
        owner("mongodb://fixture.test")
