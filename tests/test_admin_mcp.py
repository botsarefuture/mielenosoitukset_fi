import hashlib
import jwt

from bson import ObjectId
from mielenosoitukset_fi.utils.tokens import create_token


def _mcp_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _rpc(method: str, params=None, request_id=1):
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}


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
        scopes=["read", "write", "admin"],
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
