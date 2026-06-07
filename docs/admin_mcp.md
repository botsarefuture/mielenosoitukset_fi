# Admin MCP

This repository now includes an MCP-compatible admin endpoint at:

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

By default, once `ADMIN_MCP.ENABLED` is on, the server now exposes a full OAuth authorization-code flow for ChatGPT / remote MCP clients:

- `GET /.well-known/oauth-authorization-server`
- `GET /.well-known/openid-configuration`
- `GET /.well-known/oauth-protected-resource/api/admin/mcp`
- `POST /api/admin/mcp/oauth/register`
- `GET|POST /api/admin/mcp/oauth/authorize`
- `POST /api/admin/mcp/oauth/token`

ChatGPT developer mode can use these endpoints directly with dynamic client registration, consent, and PKCE.

If you already have your own issuer, you can still configure the JWT validation fields above so MCP accepts externally issued bearer tokens too.

## Recommended login path

Use the OAuth flow described below for remote MCP clients. It binds MCP access
to an explicit administrator consent flow and issues a short-lived token with
the required `mcp.admin` scope.

The repository API-token system is also accepted, but every API token used for
Admin MCP must include `mcp.admin`. Only a global administrator can issue that
privileged scope. Ordinary `read`, `write`, or `admin` API tokens are rejected
by the MCP endpoint.

For bootstrap or private local use, the legacy static-token mode is still supported.
Configured static tokens remain limited by their configured `read`, `write`, or
`admin` scopes:

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

## ChatGPT OAuth flow

For the easiest ChatGPT setup:

1. Turn on developer mode in ChatGPT.
2. Add your MCP server URL:
   - `https://your-host/api/admin/mcp`
3. Pick `OAuth` authentication.
4. Leave static client credentials empty and let ChatGPT use dynamic client registration.
5. ChatGPT will register a public OAuth client, send the user to `/api/admin/mcp/oauth/authorize`, and exchange the resulting authorization code at `/api/admin/mcp/oauth/token`.

The consent screen requires a logged-in admin-capable account (`global_admin`, `admin`, `superuser`, or `god`), so regular users cannot grant MCP admin access.

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

## Current limitations

- Dynamic client registration is implemented, but CIMD is not advertised.
- OAuth access tokens are short-lived bearer JWTs intended for MCP use; refresh tokens are not issued yet.
- The first tool slice still covers only demonstrations, organizations, and support/admin cases, not the full admin dashboard surface.
