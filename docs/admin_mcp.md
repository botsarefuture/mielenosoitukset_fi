# Admin MCP

This repository now includes a token-protected MCP-compatible admin endpoint at:

- `POST /api/admin/mcp`

It exposes a first foundation slice for AI-driven admin work without going through the browser dashboard.

## Security model

Admin MCP is disabled by default. Enable it in `config.yaml`:

```yaml
ADMIN_MCP:
  ENABLED: true
  TOKENS:
    - name: codex
      sha256: "paste_sha256_here"
      scopes: ["read", "write"]
```

Use `scripts/hash_admin_mcp_token.py` to generate a SHA-256 hash for a token:

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
