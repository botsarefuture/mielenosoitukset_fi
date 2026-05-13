# Admin MCP

This repository now includes a token-protected MCP-compatible admin endpoint at:

- `POST /api/admin/mcp`

It exposes a first foundation slice for AI-driven admin work without going through the browser dashboard.

## Security model

Admin MCP is disabled by default. Enable it in `config.yaml`:

```yaml
ADMIN_MCP:
  ENABLED: true
  OAUTH:
    ENABLED: true
    ISSUER: "https://auth.example.test"
    AUDIENCE: "mielenosoitukset-admin-mcp"
    JWT_ALGORITHMS: ["HS256"]
    JWT_SHARED_SECRET: "replace-with-oauth-resource-secret"
    REQUIRED_SCOPES: ["mcp.admin"]
```

This is the recommended mode for OpenAI-compatible remote MCP authentication: OpenAI can pass your OAuth access token to the MCP server as a bearer token, and the server validates the JWT claims locally.

## Easiest login path right now

The easiest supported way to use this MCP server is to reuse the repository's **existing API token system**.

That means you do **not** need a separate MCP-specific login product before trying it.

Practical flow:

1. Get API token access approved for your user in the existing developer/API-token flow.
2. Create a token with the scopes you need.
3. Pass that token to OpenAI as the MCP `authorization` bearer token.

Examples:

- personal user token: create from `/users/auth/api_token`
- developer app token: create from `/developer/apps/<app_id>/token`

If you need admin dashboard control through MCP, the token must include at least:

- `admin`

Usually you also want:

- `read`
- `write`

So the practical MCP token scope set is usually:

- `["read", "write", "admin"]`

Then use it in OpenAI's MCP tool config as the `authorization` bearer token.

For bootstrap or private local use, the legacy static-token mode is still supported:

```yaml
ADMIN_MCP:
  ENABLED: true
  TOKENS:
    - name: codex
      sha256: "paste_sha256_here"
      scopes: ["read", "write"]
```

Use `scripts/hash_admin_mcp_token.py` to generate a SHA-256 hash for a legacy static token:

```bash
python scripts/hash_admin_mcp_token.py
```

Then send the token as:

```http
Authorization: Bearer <your-token>
```

## Supported MCP methods

- `initialize`
- `ping`
- `tools/list`
- `tools/call`

## Tools in the first slice

- `list_demos`
- `get_demo`
- `create_demo`
- `update_demo`
- `list_organizations`
- `get_organization`
- `create_organization`
- `update_organization`
- `list_cases`
- `get_case`
- `add_case_note`
- `close_case`
- `reopen_case`

## Example request

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "list_demos",
    "arguments": {
      "search": "helsinki",
      "per_page": 10
    }
  }
}
```

## Scope of this foundation

This first MCP slice covers the highest-value dashboard actions for:

- demonstrations
- organizations
- support/admin cases

It does not yet expose every admin-dashboard action. The intended next expansions are:

- recurring demos
- moderation tokens and approval actions
- organization membership/invite actions
- translator/admin review workflows
- audit log reads and selected write actions

## Important limitation

This foundation implements the **resource server** side of OAuth bearer-token validation. It does **not** yet implement a full authorization server, consent UI, or dynamic client registration flow by itself.

That means:

- it is ready to accept OAuth access tokens issued by your auth system
- it is ready to accept this repo's existing API tokens directly
- it is compatible with the OpenAI-side bearer-token pattern
- but a complete end-user "Sign in with OpenAI/ChatGPT connector" flow still requires the surrounding OAuth issuer setup
