import hashlib
import base64
from urllib.parse import parse_qs, urlparse
import jwt

from bson import ObjectId
from mielenosoitukset_fi.utils.tokens import create_token


def _mcp_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _rpc(method: str, params=None, request_id=1):
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}


def _pkce_s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _mcp_client(app_factory, seeded_data):
    token = "super-secret-mcp-token"
    app = app_factory(
        ADMIN_MCP={
            "ENABLED": True,
            "TOKENS": [
                {
                    "name": "pytest",
                    "sha256": hashlib.sha256(token.encode("utf-8")).hexdigest(),
                    "scopes": ["read", "write"],
                }
            ],
        }
    )
    client = app.test_client()
    return client, token, seeded_data


def _oauth_mcp_client(app_factory, seeded_data):
    secret = "oauth-mcp-secret"
    token = jwt.encode(
        {
            "sub": "pytest-oauth-client",
            "iss": "https://auth.example.test",
            "aud": "mielenosoitukset-admin-mcp",
            "scope": "mcp.admin write read",
        },
        secret,
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


def test_admin_mcp_requires_bearer_token(app_factory, seeded_data):
    client, _, _ = _mcp_client(app_factory, seeded_data)

    response = client.post("/api/admin/mcp", json=_rpc("initialize"))

    assert response.status_code == 401
    assert response.get_json()["error"]["message"] == "Unauthorized MCP token"


def test_admin_mcp_lists_tools(app_factory, seeded_data):
    client, token, _ = _mcp_client(app_factory, seeded_data)

    init_response = client.post("/api/admin/mcp", json=_rpc("initialize"), headers=_mcp_headers(token))
    assert init_response.status_code == 200
    assert init_response.get_json()["result"]["serverInfo"]["name"] == "mielenosoitukset-admin-mcp"

    tools_response = client.post("/api/admin/mcp", json=_rpc("tools/list"), headers=_mcp_headers(token))
    tools = tools_response.get_json()["result"]["tools"]
    tool_names = {tool["name"] for tool in tools}
    assert {"list_demos", "update_demo", "list_cases", "update_organization"} <= tool_names


def test_admin_mcp_oauth_metadata_advertises_registration_and_pkce(app_factory, seeded_data):
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


def test_admin_mcp_dynamic_client_registration_and_oauth_code_flow(app_factory, seeded_data):
    app = app_factory(ADMIN_MCP={"ENABLED": True})
    client = app.test_client()

    register_response = client.post(
        "/api/admin/mcp/oauth/register",
        json={
            "client_name": "Pytest ChatGPT",
            "redirect_uris": ["https://chatgpt.com/connector/oauth/test-callback"],
            "token_endpoint_auth_method": "none",
            "scope": "mcp.admin read write",
        },
    )
    assert register_response.status_code == 201
    registered = register_response.get_json()
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
    assert "Salli MCP-yhteys?" in auth_page.get_data(as_text=True)
    assert "Pytest ChatGPT" in auth_page.get_data(as_text=True)

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
        },
        follow_redirects=False,
    )
    assert approve_response.status_code == 302
    location = approve_response.headers["Location"]
    redirect_parts = urlparse(location)
    redirect_params = parse_qs(redirect_parts.query)
    code = redirect_params["code"][0]
    assert redirect_params["state"][0] == "pytest-state"

    token_response = client.post(
        "/api/admin/mcp/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        },
    )
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


def test_admin_mcp_accepts_oauth_bearer_tokens(app_factory, seeded_data):
    client, token, _ = _oauth_mcp_client(app_factory, seeded_data)

    response = client.post("/api/admin/mcp", json=_rpc("tools/list"), headers=_mcp_headers(token))

    assert response.status_code == 200
    tool_names = {tool["name"] for tool in response.get_json()["result"]["tools"]}
    assert "list_demos" in tool_names


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


def test_admin_mcp_rejects_ordinary_api_token(app_factory, seeded_data):
    token, _ = create_token(
        user_id=seeded_data["user_id"],
        token_type="short",
        scopes=["read", "write"],
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
    assert response.get_json()["error"]["message"] == "API token missing required scope: mcp.admin"


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


def test_admin_mcp_can_add_case_note(app_factory, seeded_data, db):
    client, token, seeded = _mcp_client(app_factory, seeded_data)

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
