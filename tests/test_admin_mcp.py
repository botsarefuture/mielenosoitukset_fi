import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier
import hashlib
import io
import logging
import re
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from pymongo.collection import Collection
from bson import ObjectId
from PIL import Image

from mielenosoitukset_fi.utils.tokens import create_token
from mielenosoitukset_fi.utils.s3 import upload_image_fileobj as real_upload_image_fileobj


def _mcp_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _rpc(method: str, params=None, request_id=1):
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}


def _pkce_s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _mcp_client(app_factory, seeded_data, *, scopes=None):
    token = "super-secret-mcp-token"
    app = app_factory(
        ADMIN_MCP={
            "ENABLED": True,
            "TOKENS": [
                {
                    "name": "pytest",
                    "sha256": hashlib.sha256(token.encode("utf-8")).hexdigest(),
                    "scopes": ["read", "write"] if scopes is None else scopes,
                }
            ],
        }
    )
    client = app.test_client()
    return client, token, seeded_data


def _oauth_mcp_client(app_factory, seeded_data, *, claims=None, signing_secret=None):
    secret = "oauth-mcp-secret"
    token = jwt.encode(
        {
            "sub": "pytest-oauth-client",
            "iss": "https://auth.example.test",
            "aud": "mielenosoitukset-admin-mcp",
            "scope": "mcp.admin write read",
            **(claims or {}),
        },
        signing_secret or secret,
        algorithm="HS256",
    )
    app = app_factory(
        ADMIN_MCP={
            "ENABLED": True,
            "OAUTH": {
                "ENABLED": True,
                "ISSUER": "https://auth.example.test",
                "AUDIENCE": "mielenosoitukset-admin-mcp",
                "JWT_ALGORITHMS": ["HS256"],
                "JWT_SHARED_SECRET": secret,
                "REQUIRED_SCOPES": ["mcp.admin"],
            },
        }
    )
    client = app.test_client()
    return client, token, seeded_data


@pytest.mark.parametrize("credential", ["missing", "unknown", "basic"])
def test_admin_mcp_requires_bearer_token(app_factory, seeded_data, credential):
    client, token, _ = _mcp_client(app_factory, seeded_data)
    headers = {}
    if credential == "unknown":
        headers = _mcp_headers("unrecognized-token")
    elif credential == "basic":
        headers = {"Authorization": f"Basic {token}"}

    response = client.post("/api/admin/mcp", json=_rpc("initialize", request_id="denied"), headers=headers)

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == -32001
    assert response.get_json()["id"] == "denied"
    assert response.headers["WWW-Authenticate"].startswith("Bearer ")


def test_admin_mcp_lists_tools(app_factory, seeded_data, caplog):
    client, token, _ = _mcp_client(app_factory, seeded_data)
    caplog.set_level(logging.DEBUG)

    init_response = client.post("/api/admin/mcp", json=_rpc("initialize", request_id="initialize"), headers=_mcp_headers(token))
    assert init_response.status_code == 200
    assert init_response.get_json()["id"] == "initialize"
    assert init_response.get_json()["result"]["serverInfo"]["name"] == "mielenosoitukset-admin-mcp"

    tools_response = client.post("/api/admin/mcp", json=_rpc("tools/list", request_id="catalog"), headers=_mcp_headers(token))
    assert tools_response.status_code == 200
    assert tools_response.get_json()["id"] == "catalog"
    tools = tools_response.get_json()["result"]["tools"]
    tool_names = {tool["name"] for tool in tools}
    assert {"list_demos", "update_demo", "list_cases", "update_organization"} <= tool_names
    assert token not in caplog.text
    assert token[:20] not in caplog.text


def test_admin_mcp_oauth_metadata_advertises_registration_and_pkce(app_factory):
    app = app_factory(ADMIN_MCP={"ENABLED": True})
    client = app.test_client()

    metadata_response = client.get("/.well-known/oauth-authorization-server")
    resource_response = client.get("/.well-known/oauth-protected-resource/api/admin/mcp")

    assert metadata_response.status_code == 200
    metadata = metadata_response.get_json()
    assert metadata["authorization_endpoint"].endswith("/api/admin/mcp/oauth/authorize")
    assert metadata["token_endpoint"].endswith("/api/admin/mcp/oauth/token")
    assert metadata["registration_endpoint"].endswith("/api/admin/mcp/oauth/register")
    assert "S256" in metadata["code_challenge_methods_supported"]

    assert resource_response.status_code == 200
    resource_metadata = resource_response.get_json()
    assert resource_metadata["resource"].endswith("/api/admin/mcp")
    assert resource_metadata["authorization_servers"]


def _registered_oauth_client(app_factory, *, auth_method="none"):
    app = app_factory(ADMIN_MCP={"ENABLED": True})
    client = app.test_client()

    register_response = client.post(
        "/api/admin/mcp/oauth/register",
        json={
            "client_name": "Pytest ChatGPT",
            "redirect_uris": ["https://chatgpt.com/connector/oauth/test-callback"],
            "token_endpoint_auth_method": auth_method,
            "scope": "mcp.admin read write",
        },
    )
    assert register_response.status_code == 201
    registered = register_response.get_json()

    return app, client, registered


def _approved_oauth_code(client, registered, seeded_data):
    client_id = registered["client_id"]
    redirect_uri = registered["redirect_uris"][0]

    with client.session_transaction() as session:
        session["_user_id"] = str(seeded_data["admin_id"])
        session["_fresh"] = True

    code_verifier = "pytest-code-verifier-123456789"
    auth_page = client.get(
        "/api/admin/mcp/oauth/authorize",
        query_string={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "mcp.admin read write",
            "state": "pytest-state",
            "code_challenge": _pkce_s256(code_verifier),
            "code_challenge_method": "S256",
        },
    )
    assert auth_page.status_code == 200
    assert "Pytest ChatGPT" in auth_page.get_data(as_text=True)
    csrf_token = re.search(r'name="csrf_token" value="([^"]+)"', auth_page.get_data(as_text=True))[1]

    approve_response = client.post(
        "/api/admin/mcp/oauth/authorize",
        data={
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "mcp.admin read write",
            "state": "pytest-state",
            "code_challenge": _pkce_s256(code_verifier),
            "code_challenge_method": "S256",
            "decision": "approve",
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )
    assert approve_response.status_code == 302
    location = approve_response.headers["Location"]
    redirect_parts = urlparse(location)
    redirect_params = parse_qs(redirect_parts.query)
    code = redirect_params["code"][0]
    assert redirect_params["state"][0] == "pytest-state"

    return {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }


def _exchange_oauth_code(client, registered, exchange, secret):
    data = dict(exchange)
    headers = {}
    method = registered["token_endpoint_auth_method"]
    if method == "client_secret_post" and secret is not None:
        data["client_secret"] = secret
    elif method == "client_secret_basic" and secret is not None:
        credentials = base64.b64encode(f"{registered['client_id']}:{secret}".encode()).decode("ascii")
        headers["Authorization"] = f"Basic {credentials}"
        data.pop("client_id")
    return client.post("/api/admin/mcp/oauth/token", data=data, headers=headers)


@pytest.mark.parametrize("auth_method", ["none", "client_secret_post", "client_secret_basic"])
def test_admin_mcp_dynamic_client_registration_and_oauth_code_flow(app_factory, seeded_data, auth_method):
    _, client, registered = _registered_oauth_client(app_factory, auth_method=auth_method)
    exchange = _approved_oauth_code(client, registered, seeded_data)
    token_response = _exchange_oauth_code(client, registered, exchange, registered.get("client_secret"))
    assert token_response.status_code == 200
    token_payload = token_response.get_json()
    assert token_payload["token_type"] == "Bearer"
    assert "mcp.admin" in token_payload["scope"]

    mcp_response = client.post(
        "/api/admin/mcp",
        json=_rpc("tools/list"),
        headers=_mcp_headers(token_payload["access_token"]),
    )
    assert mcp_response.status_code == 200
    tool_names = {tool["name"] for tool in mcp_response.get_json()["result"]["tools"]}
    assert "list_demos" in tool_names

    replay = _exchange_oauth_code(client, registered, exchange, registered.get("client_secret"))
    assert replay.status_code == 400
    assert replay.get_json()["error"] == "invalid_grant"
    assert "access_token" not in replay.get_json()


@pytest.mark.parametrize("auth_method", ["client_secret_post", "client_secret_basic"])
def test_admin_mcp_oauth_confidential_client_requires_secret(app_factory, seeded_data, db, auth_method):
    _, client, registered = _registered_oauth_client(app_factory, auth_method=auth_method)
    exchange = _approved_oauth_code(client, registered, seeded_data)
    for secret in (None, "wrong-client-secret"):
        denied = _exchange_oauth_code(client, registered, exchange, secret)
        assert denied.status_code == 401
        payload = denied.get_json()
        assert payload["error"] == "invalid_client"
        assert "access_token" not in payload
        assert db.oauth_authorization_codes.find_one({"code": exchange["code"]})["used_at"] is None
    allowed = _exchange_oauth_code(client, registered, exchange, registered["client_secret"])
    assert allowed.status_code == 200
    assert allowed.get_json()["access_token"]


@pytest.mark.parametrize("fault", ["verifier", "missing_verifier", "redirect", "client", "expired", "unknown"])
def test_admin_mcp_oauth_code_rejects_invalid_exchange(app_factory, seeded_data, db, fault):
    _, client, registered = _registered_oauth_client(app_factory)
    exchange = _approved_oauth_code(client, registered, seeded_data)
    invalid = dict(exchange)
    if fault == "verifier":
        invalid["code_verifier"] = "wrong-verifier"
    elif fault == "missing_verifier":
        invalid.pop("code_verifier")
    elif fault == "redirect":
        invalid["redirect_uri"] += "/other"
    elif fault == "client":
        other = client.post("/api/admin/mcp/oauth/register", json={
            "redirect_uris": registered["redirect_uris"],
            "token_endpoint_auth_method": "none",
        })
        assert other.status_code == 201
        invalid["client_id"] = other.get_json()["client_id"]
    elif fault == "expired":
        db.oauth_authorization_codes.update_one({"code": exchange["code"]}, {
            "$set": {"expires_at": datetime(2000, 1, 1, tzinfo=timezone.utc)},
        })
    elif fault == "unknown":
        invalid["code"] = "unknown-authorization-code"

    response = client.post("/api/admin/mcp/oauth/token", data=invalid)
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["error"] == ("invalid_request" if fault == "missing_verifier" else "invalid_grant")
    assert "access_token" not in payload
    assert db.oauth_authorization_codes.find_one({"code": exchange["code"]})["used_at"] is None
    if fault != "expired":
        # Rejected attempts must not consume the legitimate client's code.
        assert client.post("/api/admin/mcp/oauth/token", data=exchange).status_code == 200


def test_admin_mcp_oauth_code_consumption_is_atomic(app_factory, seeded_data, monkeypatch):
    app, client, registered = _registered_oauth_client(app_factory)
    exchange = _approved_oauth_code(client, registered, seeded_data)
    barrier = Barrier(2)
    original_find_one = Collection.find_one

    def synchronized_lookup(collection, query=None, *args, **kwargs):
        document = original_find_one(collection, query, *args, **kwargs)
        if collection.name == "oauth_authorization_codes" and query == {"code": exchange["code"]}:
            # Both requests read the same real unused record before either writes.
            barrier.wait(timeout=10)
        return document

    monkeypatch.setattr(Collection, "find_one", synchronized_lookup)

    def exchange_code():
        with app.test_client() as independent_client:
            response = independent_client.post("/api/admin/mcp/oauth/token", data=exchange)
            return response.status_code, response.get_json()

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: exchange_code(), range(2)))
    assert sorted(status for status, _ in responses) == [200, 400]
    success = next(payload for status, payload in responses if status == 200)
    failure = next(payload for status, payload in responses if status == 400)
    assert success["access_token"]
    assert failure["error"] == "invalid_grant"
    assert "access_token" not in failure


@pytest.mark.parametrize("role", ["user", "admin"])
def test_admin_mcp_oauth_consent_rechecks_global_authority(app_factory, seeded_data, db, role):
    _, client, registered = _registered_oauth_client(app_factory)
    with client.session_transaction() as state:
        state["_user_id"] = str(seeded_data["admin_id"])
        state["_fresh"] = True
    data = {
        "client_id": registered["client_id"],
        "redirect_uri": registered["redirect_uris"][0],
        "response_type": "code",
        "scope": "mcp.admin read write",
        "decision": "approve",
    }
    page = client.get("/api/admin/mcp/oauth/authorize", query_string=data)
    assert page.status_code == 200
    csrf_token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True))[1]
    db.users.update_one({"_id": seeded_data["admin_id"]}, {"$set": {"role": role, "global_admin": False}})
    before = db.oauth_authorization_codes.count_documents({})

    assert client.get("/api/admin/mcp/oauth/authorize", query_string=data).status_code == 403
    denied = client.post("/api/admin/mcp/oauth/authorize", data={**data, "csrf_token": csrf_token})
    assert denied.status_code == 403
    assert db.oauth_authorization_codes.count_documents({}) == before


def test_admin_mcp_oauth_consent_requires_csrf(app_factory, seeded_data, db):
    app, client, registered = _registered_oauth_client(app_factory)
    with client.session_transaction() as state:
        state["_user_id"] = str(seeded_data["admin_id"])
        state["_fresh"] = True
    data = {
        "client_id": registered["client_id"],
        "redirect_uri": registered["redirect_uris"][0],
        "scope": "mcp.admin read write",
        "decision": "approve",
    }
    before = db.oauth_authorization_codes.count_documents({})
    missing = client.post("/api/admin/mcp/oauth/authorize", data=data)
    assert missing.status_code == 403
    assert db.oauth_authorization_codes.count_documents({}) == before

    page = client.get("/api/admin/mcp/oauth/authorize", query_string={**data, "response_type": "code"})
    assert page.status_code == 200
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True))[1]
    other = app.test_client()
    with other.session_transaction() as state:
        state["_user_id"] = str(seeded_data["admin_id"])
        state["_fresh"] = True
    other_page = other.get("/api/admin/mcp/oauth/authorize", query_string={**data, "response_type": "code"})
    assert other_page.status_code == 200
    other_token = re.search(r'name="csrf_token" value="([^"]+)"', other_page.get_data(as_text=True))[1]
    for invalid in ("incorrect", "väärä", other_token):
        denied = client.post("/api/admin/mcp/oauth/authorize", data={**data, "csrf_token": invalid})
        assert denied.status_code == 403
        assert db.oauth_authorization_codes.count_documents({}) == before

    declined = client.post("/api/admin/mcp/oauth/authorize", data={**data, "decision": "deny", "csrf_token": token})
    assert declined.status_code == 302
    assert parse_qs(urlparse(declined.headers["Location"]).query)["error"] == ["access_denied"]
    assert db.oauth_authorization_codes.count_documents({}) == before

    allowed = client.post("/api/admin/mcp/oauth/authorize", data={**data, "csrf_token": token})
    assert allowed.status_code == 302
    assert db.oauth_authorization_codes.count_documents({}) == before + 1


def test_admin_mcp_accepts_oauth_bearer_tokens(app_factory, seeded_data):
    client, token, _ = _oauth_mcp_client(app_factory, seeded_data)

    response = client.post("/api/admin/mcp", json=_rpc("tools/list"), headers=_mcp_headers(token))

    assert response.status_code == 200
    tool_names = {tool["name"] for tool in response.get_json()["result"]["tools"]}
    assert "list_demos" in tool_names


@pytest.mark.parametrize("fault,status", [
    ("signature", 401), ("issuer", 401), ("audience", 401),
    ("expiry", 401), ("required_scope", 403),
])
def test_admin_mcp_rejects_invalid_oauth_bearer(app_factory, seeded_data, fault, status):
    changes = {
        "issuer": {"iss": "https://untrusted.example.test"},
        "audience": {"aud": "unrelated-resource"},
        "expiry": {"exp": 1},
        "required_scope": {"scope": "read write"},
    }
    client, token, _ = _oauth_mcp_client(
        app_factory, seeded_data, claims=changes.get(fault),
        signing_secret="wrong-secret" if fault == "signature" else None,
    )
    response = client.post("/api/admin/mcp", json=_rpc("tools/list", request_id="invalid-oauth"), headers=_mcp_headers(token))
    assert response.status_code == status
    payload = response.get_json()
    assert "result" not in payload
    assert payload["error"]["code"] == (-32003 if status == 403 else -32001)
    assert payload["id"] == "invalid-oauth"


@pytest.mark.parametrize("tool", ["add_case_note", "update_organization", "create_demo"])
def test_admin_mcp_read_only_token_cannot_mutate(app_factory, seeded_data, db, tool):
    client, token, seeded = _mcp_client(app_factory, seeded_data, scopes=["read"])
    listing = client.post("/api/admin/mcp", json=_rpc("tools/call", {"name": "list_demos"}), headers=_mcp_headers(token))
    assert listing.status_code == 200
    assert listing.get_json()["result"]["structuredContent"]["items"]
    arguments = {
        "add_case_note": {"case_id": str(seeded["case_id"]), "note": "Blocked note"},
        "update_organization": {"organization_id": str(seeded["org_id"]), "patch": {"website": "https://example.test/blocked"}},
        "create_demo": {"title": "Blocked creation", "date": "2026-09-01", "start_time": "16:00", "end_time": "18:00", "city": "Helsinki", "address": "MCP Street 1"},
    }
    original_case = db.cases.find_one({"_id": seeded["case_id"]})
    original_org = db.organizations.find_one({"_id": seeded["org_id"]})
    demo_count = db.demonstrations.count_documents({})
    response = client.post("/api/admin/mcp", json=_rpc("tools/call", {"name": tool, "arguments": arguments[tool]}), headers=_mcp_headers(token))
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == -32003
    assert db.cases.find_one({"_id": seeded["case_id"]}) == original_case
    assert db.organizations.find_one({"_id": seeded["org_id"]}) == original_org
    assert db.demonstrations.count_documents({}) == demo_count


def test_admin_mcp_accepts_existing_api_tokens(app_factory, seeded_data):
    token, _ = create_token(
        user_id=seeded_data["admin_id"],
        token_type="short",
        scopes=["read", "write", "mcp.admin"],
        category="user",
    )
    app = app_factory(
        ADMIN_MCP={
            "ENABLED": True,
        }
    )
    client = app.test_client()

    response = client.post("/api/admin/mcp", json=_rpc("tools/list"), headers=_mcp_headers(token))

    assert response.status_code == 200
    tool_names = {tool["name"] for tool in response.get_json()["result"]["tools"]}
    assert "list_cases" in tool_names


@pytest.mark.parametrize("scopes", [["read", "write"], ["admin"]])
def test_admin_mcp_rejects_api_token_without_mcp_scope(app_factory, seeded_data, scopes):
    token, _ = create_token(
        user_id=seeded_data["user_id"],
        token_type="short",
        scopes=scopes,
        category="user",
    )
    app = app_factory(ADMIN_MCP={"ENABLED": True})
    client = app.test_client()

    response = client.post(
        "/api/admin/mcp",
        json=_rpc("tools/list"),
        headers=_mcp_headers(token),
    )

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == -32003


def test_admin_mcp_can_search_demos(app_factory, seeded_data):
    client, token, seeded = _mcp_client(app_factory, seeded_data)

    response = client.post(
        "/api/admin/mcp",
        json=_rpc("tools/call", {"name": "list_demos", "arguments": {"search": "Climate March"}}),
        headers=_mcp_headers(token),
    )

    assert response.status_code == 200
    payload = response.get_json()["result"]["structuredContent"]
    assert payload["items"]
    assert any(item["_id"] == str(seeded["demo_id"]) for item in payload["items"])
    assert str(seeded["pending_demo_id"]) not in {item["_id"] for item in payload["items"]}
    assert payload["total"] == 1


def test_admin_mcp_can_add_case_note(app_factory, seeded_data, db):
    client, token, seeded = _mcp_client(app_factory, seeded_data)
    original_notes = db.cases.find_one({"_id": seeded["case_id"]})["action_logs"]

    response = client.post(
        "/api/admin/mcp",
        json=_rpc(
            "tools/call",
            {
                "name": "add_case_note",
                "arguments": {
                    "case_id": str(seeded["case_id"]),
                    "note": "Reviewed from MCP",
                    "actor": "pytest-mcp",
                },
            },
        ),
        headers=_mcp_headers(token),
    )

    assert response.status_code == 200
    case_doc = db.cases.find_one({"_id": seeded["case_id"]})
    assert case_doc["action_logs"][-1]["note"] == "Reviewed from MCP"
    assert case_doc["action_logs"][-1]["admin"] == "pytest-mcp"
    assert case_doc["action_logs"][-1]["action_type"] == "internal_note"
    assert case_doc["action_logs"][:-1] == original_notes


def test_admin_mcp_can_update_organization(app_factory, seeded_data, db):
    client, token, seeded = _mcp_client(app_factory, seeded_data)

    response = client.post(
        "/api/admin/mcp",
        json=_rpc(
            "tools/call",
            {
                "name": "update_organization",
                "arguments": {
                    "organization_id": str(seeded["org_id"]),
                    "patch": {"website": "https://example.test/mcp-updated"},
                },
            },
        ),
        headers=_mcp_headers(token),
    )

    assert response.status_code == 200
    organization = db.organizations.find_one({"_id": seeded["org_id"]})
    assert organization["website"] == "https://example.test/mcp-updated"


def test_admin_mcp_can_create_demo(app_factory, seeded_data, db):
    client, token, _ = _mcp_client(app_factory, seeded_data)

    response = client.post(
        "/api/admin/mcp",
        json=_rpc(
            "tools/call",
            {
                "name": "create_demo",
                "arguments": {
                    "title": "MCP Created Demo",
                    "date": "2026-09-01",
                    "start_time": "16:00",
                    "end_time": "18:00",
                    "city": "Helsinki",
                    "address": "MCP Street 1",
                    "description": "Created through MCP.",
                    "tags": ["mcp", "admin"],
                },
            },
        ),
        headers=_mcp_headers(token),
    )

    assert response.status_code == 200
    created_payload = response.get_json()["result"]["structuredContent"]
    created_demo = db.demonstrations.find_one({"_id": ObjectId(created_payload["demo_id"])})
    assert created_demo["title"] == "MCP Created Demo"
    assert created_demo["city"] == "Helsinki"


def _call_tool(client, token, name, arguments):
    return client.post(
        "/api/admin/mcp",
        json=_rpc("tools/call", {"name": name, "arguments": arguments}),
        headers=_mcp_headers(token),
    )


def _image_base64():
    stream = io.BytesIO()
    Image.new("RGB", (12, 12), "red").save(stream, format="PNG")
    return base64.b64encode(stream.getvalue()).decode("ascii")


def test_mcp_schema_describes_freeform_organizers_optional_fields_and_uploads(app_factory, seeded_data):
    client, token, _ = _mcp_client(app_factory, seeded_data)
    response = client.post("/api/admin/mcp", json=_rpc("tools/list"), headers=_mcp_headers(token))
    tools = {tool["name"]: tool for tool in response.get_json()["result"]["tools"]}
    schema = tools["create_demo"]["inputSchema"]
    assert "end_time" not in schema["required"]
    organizer_schema = schema["properties"]["organizers"]
    record_schema = next(item for item in organizer_schema["items"]["anyOf"] if item["type"] == "object")
    assert {"name", "organization_id", "email", "website"} <= record_schema["properties"].keys()
    assert record_schema["anyOf"] == [{"required": ["name"]}, {"required": ["organization_id"]}]
    assert "description" not in tools["create_organization"]["inputSchema"]["required"]
    assert "upload_image" in tools
    assert {"cover_picture", "img", "preview_image", "gallery_images"} <= schema["properties"].keys()


def test_mcp_creates_demo_without_end_time_or_organizer_contact(app_factory, seeded_data, db):
    client, token, seeded = _mcp_client(app_factory, seeded_data)
    org = db.organizations.find_one({"_id": seeded["org_id"]})
    response = _call_tool(client, token, "create_demo", {
        "title": "Optional details", "date": "2026-11-07", "start_time": "13:00",
        "city": "Helsinki", "address": "Rautatientori",
        "organizers": [{"name": "Unregistered group"}, str(seeded["org_id"])],
        "cover_picture": "https://example.test/poster.jpg",
    })
    payload = response.get_json()["result"]["structuredContent"]
    demo = db.demonstrations.find_one({"_id": ObjectId(payload["demo_id"])})
    assert demo["end_time"] is None
    assert demo["event_type"] == "OTHER"
    assert demo["cover_picture"] == "https://example.test/poster.jpg"
    assert demo["organizers"][0]["name"] == "Unregistered group"
    assert demo["organizers"][0]["email"] == ""
    linked = demo["organizers"][1]
    assert linked["organization_id"] == seeded["org_id"]
    assert linked["name"] == org["name"]
    assert linked["email"] == org["email"]
    # The dashboard must show populated rows rather than blank cards.
    with client.session_transaction() as session:
        session["_user_id"] = str(seeded["admin_id"])
        session["_fresh"] = True
    page = client.get(f"/admin/demo/edit_demo/{payload['demo_id']}")
    assert page.status_code == 200
    assert "Unregistered group" in page.get_data(as_text=True)
    assert org["name"] in page.get_data(as_text=True)


def test_mcp_organizer_update_preserves_metadata_and_privacy(app_factory, seeded_data, db):
    client, token, seeded = _mcp_client(app_factory, seeded_data)
    record_id = ObjectId()
    db.demonstrations.update_one({"_id": seeded["demo_id"]}, {"$set": {"organizers": [{
        "_id": record_id, "name": "Old name", "email": "", "website": "",
        "logo": "https://example.test/group-logo.jpg",
    }]}})
    response = _call_tool(client, token, "update_demo", {
        "demo_id": str(seeded["demo_id"]), "patch": {
            "start_time": "14:15", "end_time": None,
            "organizers": [{"_id": str(record_id), "name": "New name", "is_private": True,
                            "show_name_public": False, "show_email_public": False}],
        },
    })
    assert "error" not in response.get_json()
    demo = db.demonstrations.find_one({"_id": seeded["demo_id"]})
    assert demo["start_time"] == "14:15:00"
    assert demo["end_time"] is None
    organizer = demo["organizers"][0]
    assert organizer["_id"] == record_id
    assert organizer["logo"] == "https://example.test/group-logo.jpg"
    assert organizer["name"] == "New name"
    assert organizer["is_private"] is True
    assert organizer["show_name_public"] is False
    assert organizer["show_email_public"] is False


@pytest.mark.parametrize("organizers", [
    "not-an-array", [1], [{}], [{"email": "contact@example.test"}],
    [{"organization_id": "not-an-id"}], [{"organization_id": str(ObjectId())}],
    [{"name": "Group"}, {"name": "Group"}],
])
def test_mcp_rejects_invalid_organizers_without_changing_demo(app_factory, seeded_data, db, organizers):
    client, token, seeded = _mcp_client(app_factory, seeded_data)
    before = db.demonstrations.find_one({"_id": seeded["demo_id"]})
    response = _call_tool(client, token, "update_demo", {
        "demo_id": str(seeded["demo_id"]), "patch": {"title": "Should not save", "organizers": organizers},
    })
    assert response.get_json()["error"]["code"] == -32602
    assert db.demonstrations.find_one({"_id": seeded["demo_id"]}) == before


def test_mcp_creates_organization_without_description(app_factory, seeded_data, db):
    client, token, _ = _mcp_client(app_factory, seeded_data)
    response = _call_tool(client, token, "create_organization", {
        "name": "Optional description", "email": "group@example.test",
    })
    payload = response.get_json()["result"]["structuredContent"]
    assert db.organizations.find_one({"_id": ObjectId(payload["organization_id"])})["description"] == ""


@pytest.mark.parametrize("field", ["cover_picture", "img", "preview_image", "gallery_images"])
def test_mcp_upload_attaches_image_using_shared_storage(app_factory, seeded_data, db, monkeypatch, field):
    from mielenosoitukset_fi import mcp_admin_bp

    client, token, seeded = _mcp_client(app_factory, seeded_data)
    url = "https://cdn.example.test/DEM/upload.jpg"
    uploaded = []

    def upload(bucket, stream, filename, image_type):
        with Image.open(stream) as image:
            assert image.size == (12, 12)
        uploaded.append((bucket, filename, image_type))
        return url

    monkeypatch.setattr(mcp_admin_bp, "upload_image_fileobj", upload)
    if field == "gallery_images":
        db.demonstrations.update_one({"_id": seeded["demo_id"]}, {"$set": {field: ["https://example.test/existing.jpg"]}})
    response = _call_tool(client, token, "upload_image", {
        "filename": "poster.png", "data_base64": "data:image/png;base64," + _image_base64(),
        "demo_id": str(seeded["demo_id"]), "field": field,
    })
    assert response.status_code == 200
    assert response.get_json()["result"]["structuredContent"]["url"] == url
    assert uploaded == [("mielenosoitukset-test", "poster.png", "demo_pics")]
    saved = db.demonstrations.find_one({"_id": seeded["demo_id"]})[field]
    assert saved == (["https://example.test/existing.jpg", url] if field == "gallery_images" else url)


def test_mcp_upload_sets_organization_logo(app_factory, seeded_data, db, monkeypatch):
    from mielenosoitukset_fi import mcp_admin_bp

    client, token, seeded = _mcp_client(app_factory, seeded_data)
    monkeypatch.setattr(mcp_admin_bp, "upload_image_fileobj", lambda *args: "https://cdn.example.test/logo.jpg")
    response = _call_tool(client, token, "upload_image", {
        "filename": "logo.png", "data_base64": _image_base64(),
        "organization_id": str(seeded["org_id"]),
    })
    assert "error" not in response.get_json()
    assert db.organizations.find_one({"_id": seeded["org_id"]})["logo"] == "https://cdn.example.test/logo.jpg"


@pytest.mark.parametrize("source", ["auto", "automatic"])
@pytest.mark.parametrize("operation", ["upload_image", "update_demo"])
def test_mcp_user_cover_replaces_automatic_source(app_factory, seeded_data, db, monkeypatch, source, operation):
    from mielenosoitukset_fi import mcp_admin_bp

    client, token, seeded = _mcp_client(app_factory, seeded_data)
    url = "https://cdn.example.test/user-poster.jpg"
    db.demonstrations.update_one({"_id": seeded["demo_id"]}, {"$set": {
        "cover_source": source, "img": None, "gallery_images": [], "cover_picture": "https://example.test/generated.jpg",
    }})
    monkeypatch.setattr(mcp_admin_bp, "upload_image_fileobj", lambda *args: url)
    arguments = {"demo_id": str(seeded["demo_id"])}
    if operation == "upload_image":
        arguments.update({"filename": "poster.png", "data_base64": _image_base64()})
    else:
        arguments["patch"] = {"cover_picture": url}
    response = _call_tool(client, token, operation, arguments)
    assert "error" not in response.get_json()
    demo = db.demonstrations.find_one({"_id": seeded["demo_id"]})
    assert demo["cover_source"] == "user"
    assert demo["cover_picture"] == url
    page = client.get(f"/demonstration/{seeded['demo_id']}")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert '<section class="demo-gallery' in html
    assert f'<img src="{url}"' in html


@pytest.mark.parametrize("arguments", [
    {"filename": "poster.png", "data_base64": "not base64"},
    {"filename": "poster.png", "data_base64": base64.b64encode(b"not an image").decode()},
    {"filename": "poster.png", "data_base64": _image_base64(), "field": "logo"},
    {"filename": "poster.png", "data_base64": _image_base64(), "demo_id": str(ObjectId())},
    {"filename": "poster.png", "data_base64": _image_base64(), "demo_id": "invalid"},
])
def test_mcp_invalid_upload_does_not_reach_storage(app_factory, seeded_data, monkeypatch, arguments):
    from mielenosoitukset_fi import mcp_admin_bp

    client, token, _ = _mcp_client(app_factory, seeded_data)
    monkeypatch.setattr(mcp_admin_bp, "upload_image_fileobj", lambda *args: pytest.fail("Should not upload"))
    response = _call_tool(client, token, "upload_image", arguments)
    assert response.get_json()["error"]["code"] in {-32602, -32004}


def test_mcp_failed_storage_keeps_existing_image(app_factory, seeded_data, db, monkeypatch):
    from mielenosoitukset_fi import mcp_admin_bp

    client, token, seeded = _mcp_client(app_factory, seeded_data)
    before = db.demonstrations.find_one({"_id": seeded["demo_id"]})
    monkeypatch.setattr(mcp_admin_bp, "upload_image_fileobj", lambda *args: None)
    response = _call_tool(client, token, "upload_image", {
        "filename": "poster.png", "data_base64": _image_base64(), "demo_id": str(seeded["demo_id"]),
    })
    assert response.status_code == 500
    assert db.demonstrations.find_one({"_id": seeded["demo_id"]}) == before


def test_mcp_upload_runs_real_image_conversion(app_factory, seeded_data, monkeypatch):
    from mielenosoitukset_fi import mcp_admin_bp
    from mielenosoitukset_fi.utils import s3

    client, token, _ = _mcp_client(app_factory, seeded_data)
    objects = []

    class StorageClient:
        def put_object(self, **kwargs):
            objects.append(kwargs)

    monkeypatch.setattr(s3, "_s3_client", StorageClient())
    monkeypatch.setattr(mcp_admin_bp, "upload_image_fileobj", real_upload_image_fileobj)
    response = _call_tool(client, token, "upload_image", {
        "filename": "poster-without-extension", "data_base64": _image_base64(),
    })
    assert response.status_code == 200
    payload = response.get_json()["result"]["structuredContent"]
    assert payload["uploaded"] is True
    assert payload["url"].startswith("https://cdn.example.test/DEM/demo_pics-")
    assert len(objects) == 1
    assert objects[0]["ContentType"] == "image/jpeg"
    with Image.open(io.BytesIO(objects[0]["Body"])) as image:
        assert image.format == "JPEG"
        assert image.size == (12, 12)


def test_mcp_upload_requires_write_scope(app_factory, seeded_data, monkeypatch):
    from mielenosoitukset_fi import mcp_admin_bp

    client, token, _ = _mcp_client(app_factory, seeded_data)
    client.application.config["ADMIN_MCP"]["TOKENS"][0]["scopes"] = ["read"]
    monkeypatch.setattr(mcp_admin_bp, "upload_image_fileobj", lambda *args: pytest.fail("Should not upload"))
    response = _call_tool(client, token, "upload_image", {
        "filename": "poster.png", "data_base64": _image_base64(),
    })
    assert response.status_code == 403


def test_mcp_upload_checks_size_before_contacting_storage(app_factory, seeded_data, monkeypatch):
    from mielenosoitukset_fi import mcp_admin_bp

    client, token, _ = _mcp_client(app_factory, seeded_data)
    client.application.config["ADMIN_MCP"]["MAX_IMAGE_BYTES"] = 16
    monkeypatch.setattr(mcp_admin_bp, "upload_image_fileobj", lambda *args: pytest.fail("Should not upload"))
    response = _call_tool(client, token, "upload_image", {
        "filename": "poster.png", "data_base64": _image_base64(),
    })
    assert response.get_json()["error"]["code"] == -32602


@pytest.mark.parametrize("patch", [
    {"title": "Should not save", "start_time": "25:99"},
    {"title": "", "start_time": "14:15"},
    {"address": "", "start_time": "14:15"},
])
def test_mcp_invalid_update_is_atomic(app_factory, seeded_data, db, patch):
    client, token, seeded = _mcp_client(app_factory, seeded_data)
    before = db.demonstrations.find_one({"_id": seeded["demo_id"]})
    response = _call_tool(client, token, "update_demo", {
        "demo_id": str(seeded["demo_id"]), "patch": patch,
    })
    assert response.get_json()["error"]["code"] == -32602
    assert db.demonstrations.find_one({"_id": seeded["demo_id"]}) == before
