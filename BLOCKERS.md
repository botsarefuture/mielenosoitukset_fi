# Blockers and resume points

Working notes for the maintainer. Lives on branch `claude/vibrant-gates-syjhk4` only; not meant for `main`.

## Waiting for you

- **Panel host root password (pasted in a Codex thread on Nov 3) must be rotated.** Not used, not touched. Needs an approved secure procedure.
- **#1040 merge** (information pages to React): needs your merge approval after visual SHIP. Merge activates Apache routing for `/info`, `/ohjeet`, `/privacy`, `/terms`, `/upcoming/translations/` on deploy.
- **#1041 merge** (development workflow doc, includes the hero eyebrow rule).
- **#1040 note:** it extends the existing Flask `/api/session` with `?translation_join=1`, returning the existing session-bound join nonce and flash messages. Not new auth, but touches the session endpoint. Flagging for your review.

## In progress

- #1040 independent visual review of snapshot c4aae12 (390/1440, light/dark, three translation roles, no-JS guide). Captures: `/tmp/claude-0/-home-user-mielenosoitukset-fi/8469dc3e-c0fb-5022-bf64-67a8e4da67d7/scratchpad/qa/out/` (container-local). On SHIP: mark #1040 ready. On FIX: fix, recapture, new reviewer.

## Resume next

- UI-06 next item after information pages: Pride, then campaign and fundraising.
- Triage of ~18 old open PRs (Dependabot, #948 pyjwt security bump, etc.): report only, don't touch.

## Decisions I made on my own

- Removed the "Ohjekeskus" hero pill from the React guide; left it in the old Flask template (being retired).
- Local test setup: Mongo/Redis via `compose.test.yml` in Docker, Go API built from `go-api/`.
