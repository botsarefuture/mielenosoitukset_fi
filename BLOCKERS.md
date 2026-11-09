# Blockers and resume points

Working notes for the maintainer. Lives on branch `claude/vibrant-gates-syjhk4` only; not meant for `main`.
Work moved from the cloud session to a local Claude Code session on 9 November 2026.

## Waiting for you

- **Panel host root password (pasted in a Codex thread on Nov 3) must be rotated.** Not used, not touched.
- **#1040 content, now live:** the /info and translation stat tiles were removed, some sentences shortened, and the /info campaign block is a plain fourth card instead of the orange promo. Keep, or restore?
- **#1040 session endpoint, now live:** `/api/session?translation_join=1` returns the session-bound join nonce and flash messages. Not new auth, but it touches the session endpoint.
- **Report form, status and account pages:** see "Proposal: remaining public pages".

## Done on 9 November

- Merged and live: #1040 information pages, #1042 style.css cleanup, #1043 Pride, #1044 no-JS policy, #1045 contrast and listing states, #1046 campaign page, #1047 fundraising page, #1048 contact page (session scope `contact_form` approved by you), #1049 about page layout.
- No-JS policy (your decision): fallbacks stay light, are checked by assertions, and get no visual review.

## Proposal: remaining public pages

These need a backend decision before they can move, so they were not started:

- `/report`: the error report form posts to Flask with a CSRF token. #1048 solved the same problem for `/contact` with an `/api/session` scope; a `/report` scope would follow that pattern but is still a session change for your approval.
- `/status`: runs Flask's health checks. Moving it needs a Go or Flask JSON endpoint for those checks.
- Account pages (`/login`, `/register`, `/settings`, password reset, MFA): authentication flows, explicitly yours to approve.

## Backlog discoveries

- Measuring no-JS visitors needs a `<noscript>` pixel and a counting endpoint; the pageview beacon only runs with JavaScript. Bots will dominate the raw count. Not started.
- At 390 the campaign form's error message is below the fold after an empty submit.
- Charcoal "Poista suodattimet" and pale grey light secondary buttons; underline next to the card invite "+"; centred guide step titles at 390.
- In the fundraising open state the MobilePay links sit far apart (same as the old Flask page).

## Dropped

- Homelab VM disk and memory resizing: not wanted (9 November).
