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
- `upload_image`
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

## Demonstration fields and organizers

`create_demo` requires title, date, start time, city and address, matching the
demonstration model. End time is optional and may be omitted or set to `null`.
`update_demo` also accepts `null` to clear an unknown end time. Both operations
normalize dates and times through the demonstration model. Event types are
`MARCH`, `STAY_STILL`, `ROAD_BLOCK`, and `OTHER` (the default).

Organizers use the dashboard's shared organizer parser. Link an existing
organization profile by ID, or use a freeform name with optional contact details:

```json
{
  "organizers": [
    {"organization_id": "66c257cd1704d4c3c19e1a57"},
    {"name": "Local action group"},
    {"name": "Another group", "email": "contact@example.test", "website": "https://example.test"}
  ]
}
```

An organization profile is **not required** to list a group as an event organizer.
Profile creation requires a name and email; its description is optional, matching
the normal admin create handler. Freeform event organizers only require a name.

For compatibility, an organizer string is interpreted as a profile ID when it is
a valid ObjectId, otherwise as a freeform name. Profile details are resolved on
the server and stored as populated organizer records, never bare strings.
Missing profiles and duplicate organizers are rejected before saving. On edits,
return the organizer's `_id` to retain its record metadata; linked profiles are
also matched by `organization_id`. The privacy fields `is_private`,
`show_name_public`, and `show_email_public` behave as in the dashboard.
An empty organizers array removes all rows.

Both create and update accept `cover_picture`, `img`, `preview_image`, and
`gallery_images` URLs. Supplied or uploaded cover replacements are marked as
user-provided so a previous automatic-cover marker cannot hide the image. Image uploads do not require an externally hosted URL.

## Uploading attached images

`upload_image` requires `filename` and `data_base64` containing image bytes encoded
as base64, or an image data URL (`data:image/png;base64,...`). A remote client must
read its own attachment and send its bytes: server-local paths are not supported.
The file is checked as an image and passed to the same S3/JPEG conversion helper
used by the dashboard.

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "upload_image",
    "arguments": {
      "filename": "poster.png",
      "data_base64": "<base64-encoded image bytes>",
      "demo_id": "<event ObjectId>",
      "field": "cover_picture"
    }
  }
}
```

- With `demo_id`, the default field is `cover_picture`; `img`, `preview_image`,
  and `gallery_images` are also supported. Gallery uploads append to existing images.
- With `organization_id`, the image sets the profile's `logo`.
- With neither target, the tool returns the public URL for later use. Do not set
  `field` without a target. Supply at most one target.

Uploads require the existing `write` scope and validate image contents rather
than imposing extra filename-extension rules on top of the admin uploader. They
reject corrupt images before contacting storage. A
failed upload leaves existing image fields unchanged. The default maximum decoded
size is 16 MiB, configurable with `ADMIN_MCP.MAX_IMAGE_BYTES`; deployment HTTP/proxy
request limits must also accommodate the base64 overhead (approximately 4/3).
The tool returns `uploaded`, `url`, and, when attached, the target ID and field.

After deploying these changes, refresh the remote client's MCP tool list so it
receives the new upload tool and organizer schemas.

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
