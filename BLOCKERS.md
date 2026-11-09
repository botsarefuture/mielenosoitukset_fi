# Blockers and resume points

Working notes for the maintainer. Lives on branch `claude/vibrant-gates-syjhk4` only; not meant for `main`.

## Waiting for you

- **Panel host root password (pasted in a Codex thread on Nov 3) must be rotated.** Not used, not touched. Needs an approved secure procedure.
- **Disk/VM request (Nov 9):** see "Storage investigation" below. Needs your decision; nothing provisioned.
- **/info campaign block:** the old page showed "Tule mukaan valtakunnalliseen kampanjaan!" as an orange promo right under the hero; #1040 made it a plain fourth card. Keep it demoted, or restore the prominent placement?
- **#1040 note:** it extends the existing Flask `/api/session` with `?translation_join=1`, returning the existing session-bound join nonce and flash messages. Not new auth, but touches the session endpoint. Flagging for your review.

## Approved, waiting on a condition

- **#1040 merge** pre-approved by you (Nov 9). Visual review SHIP at 2311703. Merging when CI is green.
- **#1040 content edits to confirm:** the /info and translation stat tiles are removed, and some /info and translation sentences are shortened (the reviewer listed them in the PR). Privacy is word for word the same. Say if any should come back.

## In progress

- Pride #1043 (draft): 30 focused tests pass, including e2e. Captures done; independent review running.
- #1042: style.css cleanup, the parsed CSS is unchanged. Needs only your merge.

## Resume next

- UI-06 next item after information pages: Pride, then campaign and fundraising.
- Triage of ~18 old open PRs (Dependabot, #948 pyjwt security bump, etc.): report only, don't touch.

## Decisions I made on my own

- Removed the "Ohjekeskus" hero pill from the React guide; left it in the old Flask template (being retired).
- Local test setup: Mongo/Redis via `compose.test.yml` in Docker, Go API built from `go-api/`.

## Storage investigation (Nov 9)

- This session runs in Anthropic's managed cloud container, not on your Proxmox host. Its disk is a fixed per-session allowance (about 39G here: 9G used, 30G free after cleanup). I cannot resize it from inside, and there are no Proxmox tools or credentials here (correctly so).
- The disk-full stall was self-inflicted: the Docker test MongoDB grew to ~29G from per-test databases. Fix: run test Mongo on a size-capped tmpfs and drop test DBs; no extra capacity needed for current work.
- Proxmox VM work (resize, new VMs within 100G total) is only possible from a session that can reach your homelab through an approved route (Claude Code on your machine, or Remote Control to a folder there). Roadmap is in my Nov 9 reply; waiting for your approval and an access route.

## Backlog discoveries

- `mielenosoitukset_fi/static/css/style.css` around line 461 contains a pasted Python traceback fragment (`enosoitukset_fi/.../database_manager.py", line 90, in _init_client`). Browsers skip it as invalid CSS, but it should be removed in its own small PR.
- Guide (/ohjeet) dark theme: section headings and step titles use the global `--header_color` (#3366cc on #171b22, about 3:1). The support banner body is 3.2:1 and its kicker 2.4:1. Pre-existing; fix in a follow-up with the design-system tokens.
- Shared `public-page-header` description in dark mode is about 4.4 to 5.0:1 on the lighter gradient. Borderline; check next time the component changes.
