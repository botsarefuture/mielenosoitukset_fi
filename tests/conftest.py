import io
import importlib
import os
import shutil
import sys
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse

import pytest
import yaml
from bson import ObjectId


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


TEST_DB_NAME = f"mielenosoitukset_test_{uuid.uuid4().hex[:12]}"
TEST_SECRET = "codex-test-secret"
TEST_MONGO_URI = os.environ.get("TEST_MONGO_URI", "mongodb://127.0.0.1:27017")
TEST_REDIS_HOST = os.environ.get("TEST_REDIS_HOST", "127.0.0.1")
TEST_REDIS_PORT = int(os.environ.get("TEST_REDIS_PORT", "6379"))
TEST_MAIL_HOST = os.environ.get("TEST_MAIL_HOST", "127.0.0.1")
TEST_MAIL_PORT = int(os.environ.get("TEST_MAIL_PORT", "1025"))
TEST_S3_ENDPOINT = os.environ.get("TEST_S3_ENDPOINT", "http://127.0.0.1:4566")

_CONFIG_DIR = Path(tempfile.mkdtemp(prefix="mielenosoitukset-tests-"))
_CONFIG_PATH = _CONFIG_DIR / "config.test.yaml"
_CONFIG_PATH.write_text(
    yaml.safe_dump(
        {
            "MONGO_URI": TEST_MONGO_URI,
            "MONGO_DBNAME": TEST_DB_NAME,
            "SECRET_KEY": TEST_SECRET,
            "PORT": 5001,
            "DEBUG": False,
            "TESTING": True,
            "ENABLE_CHAT": False,
            "ENABLE_EMAIL_WORKER": False,
            "ENABLE_PANIC_THREAD": False,
            "ENABLE_BACKGROUND_JOBS": True,
            "DISABLE_BACKGROUND_JOBS": True,
            "ENFORCE_RATELIMIT": False,
            "SOCKETIO_MESSAGE_QUEUE": "",
            "CACHE_TYPE": "SimpleCache",
            "CACHE_DEFAULT_TIMEOUT": 1,
            "REDIS_HOST": TEST_REDIS_HOST,
            "REDIS_PORT": TEST_REDIS_PORT,
            "REDIS_DB": 0,
            "DEFAULT_TIMEZONE": "Europe/Helsinki",
            "MAIL": {
                "SERVER": TEST_MAIL_HOST,
                "PORT": TEST_MAIL_PORT,
                "USE_TLS": False,
                "USERNAME": "",
                "PASSWORD": "",
                "DEFAULT_SENDER": "no-reply@example.test",
            },
            "S3": {
                "ACCESS_KEY": "test",
                "SECRET_KEY": TEST_SECRET,
                "ENDPOINT_URI": TEST_S3_ENDPOINT,
                "BUCKET": "mielenosoitukset-test",
                "ALLOWED_EXTENSIONS": ["png", "jpg", "jpeg", "gif"],
                "UPLOADS_FOLDER": "uploads",
            },
            "BABEL": {
                "DEFAULT_LOCALE": "fi",
                "SUPPORTED_LOCALES": ["fi", "en", "sv"],
                "LANGUAGES": {
                    "fi": "Suomi",
                    "en": "English",
                    "sv": "Svenska",
                },
            },
            "ADMIN_EMAIL": "admin@example.test",
            "CDN_BASE_URL": "https://cdn.example.test",
        },
        sort_keys=True,
    ),
    encoding="utf-8",
)
os.environ["CONFIG_YAML_PATH"] = str(_CONFIG_PATH)

from config import Config  # noqa: E402
from mielenosoitukset_fi.database_manager import DatabaseManager  # noqa: E402


Config.reload()
DatabaseManager.reset_instance()


ALL_PERMISSIONS = sorted(
    {
        "ACCEPT_DEMO",
        "API_ADMIN",
        "API_READ",
        "API_WRITE",
        "API_WRITE_DEMOS",
        "CREATE_DEMO",
        "CREATE_ORGANIZATION",
        "CREATE_RECURRING_DEMO",
        "CREATE_USER",
        "DELETE_DEMO",
        "DELETE_ORGANIZATION",
        "DELETE_RECURRING_DEMO",
        "DELETE_USER",
        "EDIT_DEMO",
        "EDIT_ORGANIZATION",
        "EDIT_RECURRING_DEMO",
        "EDIT_USER",
        "FORCE_PASSWORD_CHANGE",
        "GENERATE_EDIT_LINK",
        "INVITE_TO_ORGANIZATION",
        "KAMPANJA",
        "LIST_CASES",
        "LIST_DEMOS",
        "LIST_ORGANIZATIONS",
        "LIST_RECURRING_DEMOS",
        "LIST_USERS",
        "MANAGE_BACKGROUND_JOBS",
        "MANAGE_CLEARANCE",
        "VIEW_ANALYTICS",
        "VIEW_BACKGROUND_JOBS",
        "VIEW_CLEARANCE_AUDIT",
        "VIEW_DEMO",
        "VIEW_LOGS",
        "VIEW_ORGANIZATION",
        "VIEW_USER",
    }
)


class FakeHTTPResponse:
    def __init__(self, payload=None, status_code=200, text="OK"):
        self._payload = payload if payload is not None else [{"lat": "60.1699", "lon": "24.9384"}]
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSMTP:
    def __init__(self, *args, **kwargs):
        self.messages = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def starttls(self):
        return None

    def login(self, *args, **kwargs):
        return None

    def sendmail(self, sender, recipients, message):
        self.messages.append((sender, recipients, message))
        return {}


def _make_upload_stub(prefix):
    def _upload_stub(bucket_name, fileobj, filename, image_type):
        safe_name = filename or "upload.jpg"
        return f"https://cdn.example.test/{prefix}/{image_type}/{safe_name}"

    return _upload_stub


@contextmanager
def _serve_app(app):
    from werkzeug.serving import make_server

    server = make_server("127.0.0.1", 0, app)
    port = server.socket.getsockname()[1]
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _allow_local_requests(route):
    parsed = urlparse(route.request.url)
    if parsed.scheme in {"data", "blob", "about"}:
        route.continue_()
        return
    if parsed.hostname in {"127.0.0.1", "localhost", None}:
        route.continue_()
        return
    route.abort()


def _user_doc(username, email, password, **updates):
    from mielenosoitukset_fi.users.models import User

    doc = User.create_user(username=username, password=password, email=email, displayname=updates.pop("displayname", username.title()))
    doc.update(
        {
            "confirmed": True,
            "active": True,
            "global_admin": False,
            "global_permissions": [],
            "role": "user",
            "api_tokens_enabled": False,
            "friends": [],
            "friend_requests": [],
            "followers": [],
            "following": [],
            "followed_organizations": [],
            "followed_recurring_demos": [],
            "bio": f"Bio for {username}",
            "last_login": datetime.utcnow(),
        }
    )
    doc.update(updates)
    return doc


def _seed_database(app, db):
    from mielenosoitukset_fi.admin.admin_demo_bp import _hash_token as hash_magic_token
    from mielenosoitukset_fi.admin.admin_demo_bp import _registry_upsert_initial, serializer
    import mielenosoitukset_fi.admin.admin_demo_bp as admin_demo_bp
    from mielenosoitukset_fi.utils.auth import generate_confirmation_token, generate_reset_token
    from mielenosoitukset_fi.utils.demo_cancellation import _hash_token as hash_cancel_token

    admin_demo_bp.mongo = db

    for collection_name in db.list_collection_names():
        if collection_name.startswith("system."):
            continue
        db[collection_name].delete_many({})

    now = datetime.utcnow()
    admin_id = ObjectId()
    user_id = ObjectId()
    friend_id = ObjectId()
    developer_id = ObjectId()
    org_id = ObjectId()
    second_org_id = ObjectId()
    demo_id = ObjectId()
    pending_demo_id = ObjectId()
    child_demo_id = ObjectId()
    recu_demo_id = ObjectId()
    case_id = ObjectId()
    suggestion_id = ObjectId()
    org_suggestion_id = ObjectId()
    history_id = ObjectId()
    app_id = ObjectId()
    scope_request_id = ObjectId()
    api_access_request_id = ObjectId()
    volunteer_id = ObjectId()
    notification_id = ObjectId()
    board_log_id = ObjectId()

    admin_doc = _user_doc(
        "admin",
        "admin@example.test",
        "AdminPass1!",
        _id=admin_id,
        displayname="Admin User",
        global_admin=True,
        global_permissions=ALL_PERMISSIONS,
        role="admin",
        api_tokens_enabled=True,
    )
    user_doc = _user_doc(
        "alice",
        "alice@example.test",
        "UserPass1!",
        _id=user_id,
        displayname="Alice Tester",
        global_permissions=["API_READ", "API_WRITE", "API_WRITE_DEMOS"],
        api_tokens_enabled=True,
        followed_organizations=[str(org_id)],
        followed_recurring_demos=[str(recu_demo_id)],
    )
    friend_doc = _user_doc(
        "bob",
        "bob@example.test",
        "FriendPass1!",
        _id=friend_id,
        displayname="Bob Friend",
    )
    developer_doc = _user_doc(
        "dev",
        "dev@example.test",
        "DevPass1!",
        _id=developer_id,
        displayname="Developer User",
        api_tokens_enabled=True,
    )

    friendship = {"user_id": friend_id, "last_updated": now}
    reverse_friendship = {"user_id": user_id, "last_updated": now}
    user_doc["friends"] = [friendship]
    friend_doc["friends"] = [reverse_friendship]

    db.users.insert_many([admin_doc, user_doc, friend_doc, developer_doc])

    db.memberships.insert_many(
        [
            {
                "_id": ObjectId(),
                "user_id": admin_id,
                "organization_id": org_id,
                "role": "owner",
                "permissions": ALL_PERMISSIONS,
            },
            {
                "_id": ObjectId(),
                "user_id": user_id,
                "organization_id": org_id,
                "role": "admin",
                "permissions": ["VIEW_ORGANIZATION", "EDIT_ORGANIZATION", "CREATE_DEMO", "EDIT_DEMO", "VIEW_DEMO"],
            },
        ]
    )

    db.organizations.insert_many(
        [
            {
                "_id": org_id,
                "name": "Test Organization",
                "description": "Primary organization used in smoke tests.",
                "email": "contact@test-org.example",
                "website": "https://example.test/org",
                "logo": None,
                "social_media_links": {"website": "https://example.test/org"},
                "verified": False,
                "invitations": [{"email": "invitee@example.test", "role": "member"}],
                "fill_url": f"/organization/{org_id}/fill",
            },
            {
                "_id": second_org_id,
                "name": "Verified Test Organization",
                "description": "Verified organization for organizer lookups.",
                "email": "bob@example.test",
                "website": "https://example.test/verified-org",
                "logo": None,
                "social_media_links": {},
                "verified": True,
                "invitations": [],
                "fill_url": None,
            },
        ]
    )

    organizer = {
        "name": "Test Organization",
        "email": "bob@example.test",
        "organization_id": second_org_id,
    }
    base_demo = {
        "title": "Climate March Helsinki",
        "date": "2026-05-01",
        "start_time": "12:00",
        "end_time": "14:00",
        "city": "Helsinki",
        "address": "Mannerheimintie 1, Helsinki",
        "description": "A seeded demonstration used for route smoke tests.",
        "approved": True,
        "hide": False,
        "rejected": False,
        "cancelled": False,
        "in_past": False,
        "organizers": [organizer],
        "tags": ["test-tag", "climate"],
        "route": [],
        "preview_image": "https://cdn.example.test/previews/demo.jpg",
        "cover_picture": "https://cdn.example.test/covers/demo.jpg",
        "gallery_images": [],
        "created_datetime": now,
        "last_modified": now,
        "running_number": 1001,
        "slug": "climate-march-helsinki",
        "formatted_date": "01.05.2026",
        "latitude": "60.1699",
        "longitude": "24.9384",
        "type": "other",
        "event_type": "other",
        "editors": [user_id],
    }
    db.demonstrations.insert_many(
        [
            {"_id": demo_id, **base_demo},
            {
                "_id": pending_demo_id,
                **base_demo,
                "title": "Pending Demonstration",
                "approved": False,
                "rejected": False,
                "running_number": 1002,
                "slug": "pending-demonstration",
            },
            {
                "_id": child_demo_id,
                **base_demo,
                "title": "Recurring Child Demo",
                "parent": demo_id,
                "running_number": 1003,
                "slug": "recurring-child-demo",
            },
        ]
    )
    db.recu_demos.insert_one(
        {
            "_id": recu_demo_id,
            "title": "Recurring Test Series",
            "description": "Series used in smoke tests.",
            "date": "2026-05-08",
            "start_time": "18:00",
            "end_time": "20:00",
            "city": "Helsinki",
            "address": "Kaivokatu 1, Helsinki",
            "approved": True,
            "hide": False,
            "tags": ["test-tag"],
            "route": [],
            "repeat_schedule": {"frequency": "weekly", "interval": 1, "weekday": None, "end_date": None},
            "created_until": now.isoformat(),
            "organizers": [organizer],
        }
    )

    db.submitters.insert_one(
        {
            "_id": ObjectId(),
            "demonstration_id": pending_demo_id,
            "submitter_name": "Alice Tester",
            "submitter_email": "alice@example.test",
            "created_at": now,
        }
    )
    db.demo_suggestions.insert_one(
        {
            "_id": suggestion_id,
            "demo_id": str(demo_id),
            "status": "pending",
            "created_at": now,
            "suggested_fields": {"title": "Updated Climate March"},
            "original_values": {"title": "Climate March Helsinki"},
            "suggested_by": {"name": "Alice Tester", "email": "alice@example.test"},
        }
    )
    db.demo_edit_history.insert_one(
        {
            "_id": history_id,
            "demo_id": str(demo_id),
            "edited_by": str(admin_id),
            "edited_at": now,
            "old_demo": {"title": "Climate March Helsinki"},
            "new_demo": {"title": "Updated Climate March"},
        }
    )

    db.cases.insert_one(
        {
            "_id": case_id,
            "type": "new_demo",
            "demo_id": pending_demo_id,
            "organization_id": org_id,
            "submitter_id": user_id,
            "submitter": {"email": "alice@example.test"},
            "error_report": {},
            "suggestion": {},
            "meta": {"closed": False},
            "action_logs": [{"timestamp": now, "admin": "admin", "action_type": "created", "note": "Seeded case"}],
            "case_history": [{"timestamp": now, "action": "created", "user": "admin", "metadata": {}}],
            "running_num": 100001,
            "created_at": now,
            "updated_at": now,
        }
    )

    db.org_edit_suggestions.insert_one(
        {
            "_id": org_suggestion_id,
            "organization_id": org_id,
            "status": {"state": "pending"},
            "fields": {
                "name": "Updated Test Organization",
                "description": "Updated org description",
                "website": "https://example.test/updated-org",
            },
            "name": "Updated Test Organization",
            "description": "Updated org description",
            "created_at": now,
            "expires_at": now + timedelta(days=7),
            "timestamp": now,
        }
    )

    db.notifications.insert_one(
        {
            "_id": notification_id,
            "user_id": user_id,
            "type": "demo_invite",
            "payload": {"demo_title": "Climate March Helsinki"},
            "link": f"/demonstration/{demo_id}",
            "created_at": now,
            "read": False,
        }
    )
    db.messages.insert_one(
        {
            "_id": ObjectId(),
            "sender_id": friend_id,
            "recipient_id": user_id,
            "type": "chat",
            "content": "Hello from Bob",
            "extra": {},
            "created_at": now,
            "read": False,
        }
    )
    db.login_logs.insert_one(
        {
            "_id": ObjectId(),
            "username": "alice",
            "user_id": user_id,
            "success": True,
            "ip": "127.0.0.1",
            "user_agent": "pytest",
            "reason": None,
            "timestamp": now,
        }
    )
    db.analytics.insert_many(
        [
            {"_id": ObjectId(), "demo_id": demo_id, "timestamp": now.replace(tzinfo=timezone.utc), "session_id": "s1"},
            {"_id": ObjectId(), "demo_id": demo_id, "timestamp": now.replace(tzinfo=timezone.utc), "session_id": "s2"},
            {"_id": ObjectId(), "demo_id": pending_demo_id, "timestamp": now.replace(tzinfo=timezone.utc), "session_id": "s3"},
        ]
    )

    db.developer_apps.insert_one(
        {
            "_id": app_id,
            "name": "Seeded Developer App",
            "description": "Used by developer route smoke tests.",
            "owner_id": developer_id,
            "client_id": "client-id",
            "client_secret": "client-secret",
            "created_at": now,
            "allowed_scopes": ["read", "write"],
        }
    )
    db.developer_scope_requests.insert_one(
        {
            "_id": scope_request_id,
            "app_id": app_id,
            "user_id": developer_id,
            "scopes": ["write"],
            "reason": "Need write access for smoke tests.",
            "status": "pending",
            "requested_at": now,
            "current_scopes": ["read"],
        }
    )
    db.api_token_requests.insert_one(
        {
            "_id": api_access_request_id,
            "user_id": developer_id,
            "username": "dev",
            "requested_at": now,
            "status": "pending",
            "reason": "Need API access for smoke tests.",
        }
    )
    db.api_tokens.insert_many(
        [
            {
                "_id": ObjectId(),
                "user_id": developer_id,
                "app_id": app_id,
                "token": "hashed-token",
                "type": "short",
                "category": "app",
                "scopes": ["read"],
                "expires_at": now.replace(tzinfo=timezone.utc) + timedelta(days=2),
                "created_at": now.replace(tzinfo=timezone.utc),
            },
            {
                "_id": ObjectId(),
                "user_id": user_id,
                "token": "hashed-user-token",
                "type": "short",
                "category": "user",
                "scopes": ["read"],
                "expires_at": now.replace(tzinfo=timezone.utc) + timedelta(days=2),
                "created_at": now.replace(tzinfo=timezone.utc),
            },
        ]
    )

    volunteer_token = "volunteer-confirm-token"
    db.volunteers.insert_one(
        {
            "_id": volunteer_id,
            "name": "Volunteer User",
            "email": "volunteer@example.test",
            "city": "Helsinki",
            "notes": "",
            "confirmed": False,
            "confirmation_token": volunteer_token,
            "confirmation_expires": now + timedelta(days=1),
        }
    )

    db.board_audit_logs.insert_one(
        {
            "_id": board_log_id,
            "user_id": str(user_id),
            "action": "approved",
            "granted_by": "admin",
            "timestamp": now,
        }
    )

    cancel_token = "cancel-demo-token"
    db.demo_cancellation_tokens.insert_one(
        {
            "_id": ObjectId(),
            "token_hash": hash_cancel_token(cancel_token),
            "demo_id": demo_id,
            "organizer_email": "bob@example.test",
            "organizer_name": "Bob Friend",
            "organization_id": second_org_id,
            "official_contact": True,
            "created_at": now,
            "expires_at": now + timedelta(days=30),
            "used_at": None,
        }
    )

    with app.app_context():
        confirmation_token = generate_confirmation_token("alice@example.test")
        reset_token = generate_reset_token("alice@example.test")
        preview_token = serializer.dumps(str(pending_demo_id), salt="preview-demo")
        approve_token = serializer.dumps(str(pending_demo_id), salt="approve-demo")
        reject_token = serializer.dumps(str(pending_demo_id), salt="reject-demo")
        edit_token = serializer.dumps(str(demo_id), salt="edit-demo")

        _registry_upsert_initial(hash_magic_token(preview_token), "preview", str(pending_demo_id), creator="pytest")
        _registry_upsert_initial(hash_magic_token(approve_token), "approve", str(pending_demo_id), creator="pytest")
        _registry_upsert_initial(hash_magic_token(reject_token), "reject", str(pending_demo_id), creator="pytest")
        _registry_upsert_initial(hash_magic_token(edit_token), "edit", str(demo_id), creator="pytest")

    return {
        "admin_id": admin_id,
        "user_id": user_id,
        "friend_id": friend_id,
        "developer_id": developer_id,
        "org_id": org_id,
        "demo_id": demo_id,
        "pending_demo_id": pending_demo_id,
        "child_demo_id": child_demo_id,
        "recu_demo_id": recu_demo_id,
        "case_id": case_id,
        "history_id": history_id,
        "suggestion_id": suggestion_id,
        "org_suggestion_id": org_suggestion_id,
        "app_id": app_id,
        "scope_request_id": scope_request_id,
        "api_access_request_id": api_access_request_id,
        "volunteer_id": volunteer_id,
        "confirmation_token": confirmation_token,
        "reset_token": reset_token,
        "cancel_token": cancel_token,
        "preview_token": preview_token,
        "approve_token": approve_token,
        "reject_token": reject_token,
        "edit_token": edit_token,
        "volunteer_token": volunteer_token,
        "user_username": "alice",
        "friend_username": "bob",
        "developer_username": "dev",
    }


@pytest.fixture(scope="session")
def test_settings():
    return {
        "config_path": str(_CONFIG_PATH),
        "mongo_uri": TEST_MONGO_URI,
        "mongo_dbname": TEST_DB_NAME,
        "redis_host": TEST_REDIS_HOST,
        "redis_port": TEST_REDIS_PORT,
        "mail_host": TEST_MAIL_HOST,
        "mail_port": TEST_MAIL_PORT,
        "s3_endpoint": TEST_S3_ENDPOINT,
    }


@pytest.fixture(scope="session")
def test_config_path():
    return str(_CONFIG_PATH)


@pytest.fixture(autouse=True)
def ensure_test_config(test_config_path):
    os.environ["CONFIG_YAML_PATH"] = test_config_path
    Config.reload()
    DatabaseManager.reset_instance()
    yield
    os.environ["CONFIG_YAML_PATH"] = test_config_path
    Config.reload()
    DatabaseManager.reset_instance()


def _cleanup_app_resources(app):
    job_leadership = app.extensions.get("job_leadership")
    if job_leadership is not None:
        try:
            job_leadership.stop()
        except Exception:
            pass

    job_manager = app.extensions.get("job_manager")
    if job_manager is not None:
        try:
            job_manager.shutdown()
        except Exception:
            pass


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_resources():
    yield

    instance = DatabaseManager._instance
    if instance is not None:
        try:
            instance.get_db().client.drop_database(TEST_DB_NAME)
        except Exception:
            pass
        try:
            instance.close_connection()
        except Exception:
            pass
        DatabaseManager._instance = None

    DatabaseManager.close_retired_test_connections()
    shutil.rmtree(_CONFIG_DIR, ignore_errors=True)


@pytest.fixture
def db():
    return DatabaseManager.get_instance().get_db()


@pytest.fixture
def external_side_effects(monkeypatch):
    import requests
    import smtplib
    from mielenosoitukset_fi.emailer.EmailSender import EmailSender
    from mielenosoitukset_fi.utils import screenshot as screenshot_module
    from mielenosoitukset_fi.utils import s3 as s3_module
    basic_routes = importlib.import_module("mielenosoitukset_fi.basic_routes")
    admin_demo_bp = importlib.import_module("mielenosoitukset_fi.admin.admin_demo_bp")
    admin_media_bp = importlib.import_module("mielenosoitukset_fi.admin.admin_media_bp")
    admin_org_bp = importlib.import_module("mielenosoitukset_fi.admin.admin_org_bp")
    auth_bp = importlib.import_module("mielenosoitukset_fi.users.BPs.auth")

    upload_stub = _make_upload_stub("uploads")

    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeHTTPResponse(), raising=True)
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: FakeHTTPResponse({"status": "ok"}), raising=True)
    monkeypatch.setattr(requests, "request", lambda *args, **kwargs: FakeHTTPResponse(), raising=True)
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP, raising=True)

    monkeypatch.setattr(EmailSender, "queue_email", lambda self, *args, **kwargs: None, raising=True)
    monkeypatch.setattr(EmailSender, "send_now", lambda self, *args, **kwargs: None, raising=True)
    monkeypatch.setattr(EmailSender, "send_email", lambda self, *args, **kwargs: None, raising=True)

    monkeypatch.setattr(s3_module, "upload_image", upload_stub, raising=True)
    monkeypatch.setattr(s3_module, "upload_image_fileobj", upload_stub, raising=True)
    monkeypatch.setattr(basic_routes, "upload_image_fileobj", upload_stub, raising=True)
    monkeypatch.setattr(admin_demo_bp, "upload_image_fileobj", upload_stub, raising=True)
    monkeypatch.setattr(admin_media_bp, "upload_image_fileobj", upload_stub, raising=True)
    monkeypatch.setattr(admin_org_bp, "upload_image_fileobj", upload_stub, raising=True)
    monkeypatch.setattr(auth_bp, "upload_image_fileobj", upload_stub, raising=True)

    monkeypatch.setattr(
        screenshot_module,
        "create_screenshot",
        lambda demo: "demo_preview/test-preview.png",
        raising=True,
    )
    monkeypatch.setattr(
        screenshot_module,
        "trigger_screenshot",
        lambda demo_id, force=False: (True, "stubbed"),
        raising=True,
    )


@pytest.fixture
def app_factory(external_side_effects):
    from mielenosoitukset_fi.app import create_app

    def _build_app(**overrides):
        config_overrides = {
            "TESTING": True,
            "ENABLE_BACKGROUND_JOBS": True,
            "DISABLE_BACKGROUND_JOBS": True,
            "ENABLE_PANIC_THREAD": False,
            "ENABLE_EMAIL_WORKER": False,
            "ENABLE_CHAT": False,
            "SOCKETIO_MESSAGE_QUEUE": "",
        }
        config_overrides.update(overrides)
        return create_app(config_overrides)

    return _build_app


@pytest.fixture
def app(app_factory):
    app = app_factory()
    try:
        yield app
    finally:
        _cleanup_app_resources(app)


@pytest.fixture
def chat_app(app_factory):
    app = app_factory(ENABLE_CHAT=True)
    try:
        yield app
    finally:
        _cleanup_app_resources(app)


@pytest.fixture
def live_server(app):
    with _serve_app(app) as base_url:
        yield base_url


@pytest.fixture
def seeded_data(app, db):
    return _seed_database(app, db)


def _client_for_user(app, user_id):
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
    return client


@pytest.fixture
def client(app, seeded_data):
    return app.test_client()


@pytest.fixture
def user_client(app, seeded_data):
    return _client_for_user(app, seeded_data["user_id"])


@pytest.fixture
def friend_client(app, seeded_data):
    return _client_for_user(app, seeded_data["friend_id"])


@pytest.fixture
def admin_client(app, seeded_data):
    return _client_for_user(app, seeded_data["admin_id"])


@pytest.fixture
def developer_client(app, seeded_data):
    return _client_for_user(app, seeded_data["developer_id"])


@pytest.fixture
def chat_seeded_data(chat_app, db):
    return _seed_database(chat_app, db)


@pytest.fixture(scope="session")
def playwright_browser():
    sync_api = pytest.importorskip("playwright.sync_api")

    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:
            pytest.skip(
                f"Playwright Chromium browser is unavailable: {exc}. "
                "Install it with 'python -m playwright install chromium'."
            )
        try:
            yield browser
        finally:
            browser.close()


@pytest.fixture
def browser_page(playwright_browser):
    context = playwright_browser.new_context(
        locale="fi-FI",
        viewport={"width": 1440, "height": 1100},
    )
    context.set_default_timeout(15000)
    context.route("**/*", _allow_local_requests)
    page = context.new_page()
    try:
        yield page
    finally:
        context.close()
