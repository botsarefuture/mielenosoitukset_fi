# Go API: fundraising details

Proposal and implementation note for `GET /api/fundraising/details`
(TODO: "Fundraising details ... a Go endpoint would let it change without a host deploy").

## Purpose

The React fundraising page (`/keräys`) imports `mielenosoitukset_fi/utils/data/fundraising.json`
at build time, so changing the dates, account or MobilePay links needs a host deploy.
The endpoint serves the same configuration from a file on the API host.

## Request and response

- `GET` or `HEAD /api/fundraising/details`, no parameters.
- 200: the configuration object exactly as in `fundraising.json` (same keys), compacted,
  `Content-Type: application/json; charset=utf-8`, `Cache-Control: no-store`.
- 503 `{"error":"fundraising details unavailable"}` when `FUNDRAISING_DETAILS_FILE` is unset,
  the file is missing, over 16 KB, empty or not a JSON object.
- Other methods: 405. It passes the existing lockdown gate like the other routes.

The server does not interpret the data. The React host applies the same rules as Flask
(`frontend/src/app/fundraising.ts`, checked against `tests/fixtures/fundraising_parity.json`),
so incomplete or unconfirmed data still never opens donations, and unsafe URLs are dropped.

## Auth and authorisation

None: the page itself is public once the campaign is published, and the data is already
shown on it. The publication gate stays with `/api/campaign/publication`. No auth change.

## Database operations

None. The source is a file named by `FUNDRAISING_DETAILS_FILE` (for example
`/etc/mielenosoitukset-api/fundraising.json`), re-read at most every five seconds.
No schema change.

## Performance

One small file read per five seconds per process, outside the response caches. The host
fetch has a 1.5 s timeout; on any failure it renders from the bundled JSON. The page is
`private, no-store` already, so no cache interaction.

## Host behaviour

`render.tsx` fetches the endpoint for `/keräys`, embeds the answer in the bootstrap
(`fundraising`) so hydration shows the same content, and passes it to `FundraisingScreen`.
Without an answer nothing is embedded and the bundled file is used. Flask's own
`utils/fundraising.py` still reads the bundled file; keep the file in the repo in sync
until Flask retires the page.

## Rollout

Deploy the Go binary, create the file with mode 0644 in a world-readable directory (the API runs as a
dynamic user and `/etc/mielenosoitukset-api` is root-only 0700), set `FUNDRAISING_DETAILS_FILE` in
`/etc/mielenosoitukset-api/environment` (back up the old file first), restart the API
(never during a backup dump: core 02:32 UTC, full Sunday 03:34 UTC). Roll back by
unsetting the variable; the host then uses the bundled copy.

**Status: active since 12 November 2026.** File `/etc/mielenosoitukset-fundraising/fundraising.json`
(copy of the bundled JSON); previous environment saved as
`environment.bak-before-fundraising-20261112`. Edit the file to change the page; no restart needed.

## Open

A MongoDB collection with an admin editing form would be the lasting source of truth, but
needs a schema and an admin UI, which need maintainer approval.
