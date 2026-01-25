# Mielenosoitukset.fi API

Welcome! This is the **public API** used by the website and external clients. It covers all non-admin endpoints currently exposed under `/api`.

If you are just getting started, read the **Quick start** and **Auth** sections first.

---

## Quick start

Base URL:

- Production: `https://mielenosoitukset.fi/api`
- Local dev: `http://127.0.0.1:5000/api`

Basic call:

```bash
curl "https://mielenosoitukset.fi/api/demonstrations?city=Helsinki"
```

---

## Auth

There are two ways to authenticate depending on the endpoint:

1) **Token auth** (API tokens)
   - Send `Authorization: Bearer <token>` header.
   - Tokens have scopes: `read`, `write`, `admin`.
   - Some endpoints require specific scopes.

2) **Session auth** (browser login cookie)
   - Used by endpoints that depend on a logged-in user (friends, invites, attending).

If an endpoint requires auth, you will get HTTP 401 without it.

---

## Rate limits

Default rate limits (global):

- 10 requests / second
- 3600 requests / hour
- 86400 requests / day

---

## Error format

Errors are returned in a consistent JSON shape:

```json
{
  "error": {
    "message": "Human readable message",
    "code": "machine_readable_code"
  },
  "status_code": 401
}
```

Common codes:

- `token_missing`, `token_invalid`, `token_expired`
- `demo_not_found`
- `insufficient_permissions`
- `auth_required`

---

## Date and time formats

- Dates: `YYYY-MM-DD` (string)
- Times: `HH:MM` or `HH:MM:SS` (string)

---

# Endpoints

Everything below is **public API** (no admin-only endpoints included). Each endpoint explicitly lists its auth requirement so there is no guessing.

---

## Demonstrations

### GET `/demonstrations`
List demonstrations with filtering + pagination.

Auth: **public (no auth required)**

Query params:

| Param | Type | Description |
| --- | --- | --- |
| `search` | string | Free text search in title |
| `city` | string | City name or comma-separated list |
| `title` | string | Title substring |
| `tag` | string | Tag filter |
| `in_past` | boolean | Include past events (`true` / `false`) |
| `parent_id` | ObjectId | Filter by recurring parent |
| `organization_id` | ObjectId | Filter by organizer org |
| `include_cancelled` | boolean | Include cancelled events |
| `max_days_till` | int | Events within N days |
| `page` | int | Pagination page |
| `per_page` | int | Page size |

Response (pagination + `cached` flag):

```json
{
  "page": 1,
  "per_page": 20,
  "total": 133,
  "total_pages": 7,
  "next_url": "...",
  "prev_url": null,
  "results": [ ... ],
  "rendered_at": "2025-01-01T12:00:00Z",
  "cached": false
}
```

---

### GET `/demonstrations/<demo_id>`
Fetch a single approved demonstration.

Auth: **token required** (scope: `read`)

Response: demonstration object.

---

### GET `/demonstrations/<demo_id>/stats`
Get analytics stats for a demo (views + likes).

Auth: **token required** (scope: `read`)

Response:

```json
{ "demo_id": "...", "views": 123, "likes": 10 }
```

---

### POST `/demonstrations/<demo_id>/like`
Increment likes. Also toggles attending as a temporary side-effect.

Auth: **token** (scope: `write`) **OR** logged-in session

Response:

```json
{ "likes": 11 }
```

---

### POST `/demonstrations/<demo_id>/unlike`
Decrement likes. Also toggles attending as a temporary side-effect.

Auth: **token** (scope: `write`) **OR** logged-in session

Response:

```json
{ "likes": 10 }
```

---

### GET `/demonstrations/<demo_id>/likes`
Get current like count.

Auth: **public (no auth required)**

Response:

```json
{ "likes": 10 }
```

---

### GET `/demonstrations/<demo_id>/attending`
Check if current user is attending.

Auth: **logged-in session required**

Response:

```json
{ "demo_id": "...", "attending": true }
```

---

### POST `/demonstrations/<demo_id>/attending`
Toggle or set attending status.

Auth: **logged-in session required**

Optional body:

```json
{ "attending": true }
```

Response:

```json
{ "demo_id": "...", "attending": true }
```

---

### POST `/demonstrations/<demo_id>/invite`
Invite friends to a demo. Sends bell notifications + chat messages.

Auth: **logged-in session required**

Body:

```json
{ "friend_ids": ["id1", "id2"] }
```

Response:

```json
{
  "demo_id": "...",
  "invited_friends": ["id1", "id2"],
  "message": "Invited 2 friends; notifications + messages sent."
}
```

---

## Friends + attending

### POST `/friends-attending`
Return which friends are attending a list of demos.

Auth: **logged-in session required** (not enforced in code, but required for meaningful results)

Body:

```json
{ "demo_ids": ["id1", "id2"] }
```

Response:

```json
{
  "id1": [ { "user_id": "...", "name": "...", "avatar": "..." } ]
}
```

---

### GET `/user/friends/`
Redirect to the user friends API (used by the UI).

Auth: **logged-in session required**

---

## Tokens (types & lifetimes)

- **Short-lived**: 48 hours. Created directly.
- **Long-lived**: 90 days. Must be created by exchanging a valid short token (`POST /api/token/long_lived`).
- **Renewal**: Only long tokens (and session tokens, internal) are renewable. Short tokens are not.
- **Categories**: User tokens (default), App tokens (created in Developer panel), System tokens (reserved), Session tokens (internal, session-bound, 7 days, renewable).
- **Scopes**: `read` (fetch data), `write` (mutate/like/invite), `submit_demonstrations` (submit demos), `admin` (admin-only; granted only if your account has admin rights).
  - App tokens can only include scopes that are allowed for the app (default: `read`; others must be approved via scope request).

Developer access & apps
-----------------------
- The Developer panel (`/developer`) is locked by default. Request access via the lock screen with a justification; admins review/approve in Kehittäjähallinta.
- New apps start with `read` scope only. Additional scopes (`write`, `submit_demonstrations`, `admin`) must be requested from the app page; admins approve/deny in Kehittäjähallinta.
- Token creation UI enforces the app’s allowed scopes; tokens cannot include scopes that are not approved for that app.

### POST `/token/renew`
Renew a token if it is close to expiry.

Auth: **token required**

Response:

```json
{ "token": "...", "expires_at": "...", "message": "Token renewed successfully" }
```

---

### POST `/token/long_lived`
Exchange a short-lived token for a long-lived token.

Auth: **token required** (must be short-lived)

Response:

```json
{ "token": "...", "expires_at": "...", "message": "Long-lived token created successfully" }
```

---

### How to get API tokens

API keys are locked until an admin approves your account. Request access in the **Settings → API-avaimet** tab (or call the request endpoint below). Once approved, you can create/list/revoke keys in the same tab. App tokens can be managed in the Developer panel (`/developer/apps`).

#### POST `/users/auth/api_token`
Create a new token.

Auth: **logged-in session required**

Body:

```json
{ "type": "short", "scopes": ["read"] }
```

Notes:
- `type` can be `short` or `long` (long is typically created via exchange; short = 48h, long = 90d).
- `scopes` can include `read`, `write`, `admin`.
- If you request `admin` scope without admin rights, it is removed automatically.
- The raw token is returned **only once**.

Response:

```json
{
  "status": "success",
  "token": "...",
  "expires_at": "2025-01-01T12:00:00",
  "scopes": ["read"],
  "type": "short"
}
```

#### GET `/users/auth/api_tokens/list`
List your existing tokens (hashed in DB; raw token is not returned again).

Auth: **logged-in session required**

Response:

```json
{
  "status": "success",
  "tokens": [
    { "_id": "...", "type": "short", "scopes": ["read"], "expires_at": "..." }
  ]
}
```

#### POST `/users/auth/api_tokens/revoke`
Revoke a token by its ID.

Auth: **logged-in session required**

Body:

```json
{ "token_id": "..." }
```

Response:

```json
{ "status": "success" }
```

#### POST `/users/auth/api_tokens/request_access`
Ask an admin to unlock API tokens for your account.

Auth: **logged-in session required**

Response:

```json
{ "status": "success", "message": "Request sent. An admin must approve API tokens for your account." }
```

---

## Notifications

These are served by the notifications blueprint at `/api/notifications`.

### GET `/notifications/`
List recent notifications for the current user.

Auth: **logged-in session required**

---

### POST `/notifications/mark-read`
Mark all notifications as read.

Auth: **logged-in session required**

---

### GET `/notifications/all`
Full notifications page (HTML).

Auth: **logged-in session required**

---

# Notes

- Some endpoints use both session + token auth. If you are calling from a server, use tokens.
- The OpenAPI spec is available at `/api-docs/openapi.yaml` but is currently partial.

---

# Contact

Questions, bugs, or API access needs?

- Support: `tuki@mielenosoitukset.fi`
- Contributors: `emilia@mielenosoitukset.fi`
