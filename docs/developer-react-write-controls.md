# `/developer` write controls in Go and React

Status: implemented behind `DEVELOPER_WRITES` (off by default), 13 November 2026. Builds on
[auth-bridge.md](auth-bridge.md) and [developer-react-proposal.md](developer-react-proposal.md).
Not active in production; activation needs a backup, an independent reviewer SHIP and the user's go.

## What moved

| Control | Where it runs now | Notes |
| --- | --- | --- |
| Create app | Go `POST /api/developer/apps` | `{name, description}`; returns the client secret once |
| Rotate client secret | Go `POST /api/developer/apps/<id>/rotate` | returns the new secret once |
| Create app token | Go `POST /api/developer/apps/<id>/token` | scopes filtered to the app's allowed set |
| Create personal token | Go `POST /api/developer/tokens` | same document as `/users/auth/api_token` |
| Revoke token | Go `DELETE /api/developer/tokens/<id>` | owner only; deletes like `/users/auth/api_tokens/revoke` |
| Scope request, access request | **Flask, unchanged** | Both send an admin email and Go has no mail sender. React posts to `/developer/apps/<id>/request_scopes` and `/developer/request_access` as before |

The Apache rule must keep sending those two POST paths and every other POST to Flask (it only claims GET
paths).

## Guards (all on the Go write routes)

- `AUTH_BRIDGE_ENABLED=true` and `DEVELOPER_WRITES_ENABLED=true`; otherwise the paths do not exist (404/405)
  and the read answers carry no `writes`/`csrf` fields, so React shows no controls.
- Signed-in session through the bridge (401/503 otherwise). Access flag `api_tokens_enabled` required for
  everything except revoke (owners may always remove their own tokens, as in Flask).
- Same origin: `Sec-Fetch-Site` must be `same-origin`; a present `Origin` must equal `AUTH_BRIDGE_ORIGIN`;
  body must be `application/json` (≤ 4 KiB).
- CSRF token: the read answers include `csrf`, an HMAC bound to the account id, valid 12 hours, keyed with a
  random per-process key (a restart only forces the page to read again). Sent back in `X-CSRF-Token`.
- Rate limit: 20 writes per minute per account (429), at most 50 apps and 150 tokens per account.
- Secrets: 12/24/32 random bytes (`secrets.token_urlsafe` sizes). Shown once in the response, stored as
  SHA-256 hex only. Responses are `no-store`.
- Audit: an `api_usage` entry per action (`developer app created`, `developer app secret rotated`,
  `developer token created`, `developer token revoked`) with user id, IP, timestamp, `source: go-api`.
  Flask's own audit is limited to refused privileged requests, which Go also refuses.

## Differences from Flask (deliberate, stricter)

1. `client_secret` is stored hashed (SHA-256 hex) in the existing `client_secret` field. Flask stores the
   plaintext for apps created there. Nothing in the code base reads the field back, so no consumer breaks;
   if a client-secret exchange is ever built it must hash the presented value and accept both formats.
2. `admin` and `mcp.admin` are refused in Go (403) for personal and app tokens. Flask requires a global
   admin plus a recent step-up for personal tokens, which only Flask can check; it does not step up for app
   tokens, but an app allowed those scopes is rare and can use the old page while the old route exists.
3. Caps and the rate limit above do not exist in Flask. Token `type` is limited to `short`, `long`, `session`
   like `create_token`.
4. Eligibility matches `create_token`: no token for suspended, inactive, banned or `god` accounts.

## Activation (needs the user's go)

1. Backup `config.yaml` and `/etc/mielenosoitukset-api/environment`.
2. Add `DEVELOPER_WRITES: true` to `config.yaml` (`AUTH_BRIDGE_SCOPES: true` must already be set), re-run the
   deploy so `configure_environment.py` writes `DEVELOPER_WRITES_ENABLED=true`, restart the API (not during a
   backup dump).
3. Only then ask the Apache session to activate the `/developer` GET rule.

## Revert

Remove `DEVELOPER_WRITES` from `config.yaml`, re-run the deploy (or delete the line from the environment
file) and restart the API: the write routes and the controls disappear and Flask serves `/developer` as before
(remove the Apache rule first if it is active). Documents created through Go stay valid: app tokens and
apps use Flask's shapes. Merge revert: `git revert` the PR; no data migration either way.
