# Pride banner carrier signup

Status: implemented behind switches that are all off, 13 November 2026. Not active in production.
The maintainer approved the mockup and collecting these signups on 13 November 2026. The index, the
switches and the first real mail each need the maintainer's go in the working session (see "Activation").

## What it does

The Pride näkyväksi page (`/pride-nakyvaksi`) calls for people to carry a Mielenosoitukset.fi banner at a
Pride event: the goal is a banner at every Pride in Finland. A visitor gives a first name or nickname, an
e-mail address and consent, and optionally an area, which Pride they would like to join (or "En tiedä vielä")
and a short note. They confirm the address from a link and are contacted later; signing up promises nothing
and can be cancelled. No phone number and no home address are asked.

This is a **second list on the fundraising reminder system** ([fundraising-reminder.md](fundraising-reminder.md)),
not a second system. Read that document for the guards, the token rules and the limits; this one lists only
what differs.

## Parts

| Part | Where | Notes |
| --- | --- | --- |
| Routes | Go, `go-api/banner_volunteer.go` on `reminderListHandler` in `fundraising_reminder.go` | `POST /api/pride-banner/volunteer`, `…/confirm`, `…/unsubscribe`. Same origin check, panic switch, rate limits, honeypot, identical answer and one-click removal as the reminder |
| Form and link page | React, `PrideVolunteer.tsx`, `PrideCarrierLink.tsx`, `pride-volunteer.ts` | The form shows only while `pride_banner.json` has `volunteer_form: true`. The link page (`/pride-nakyvaksi?kantaja=vahvista#t=…` or `…=peru#t=…`) works whatever the switch says, so a removal link never dies |
| Tokens and mail | Flask, `utils/pride_banner_volunteers.py` and the job `deliver_pride_banner_confirmations` | Reuses the reminder's token minting, link base and constants. Plain text, `List-Unsubscribe` one-click headers |
| Retention | job `purge_pride_banner_volunteers` | see below |
| Export | `python -m mielenosoitukset_fi.scripts.export_pride_banner_volunteers` | confirmed carriers as CSV on stdout; read-only; formula-safe cells |
| Data | collection `pride_banner_volunteers` | unique index on `email` |

## What differs from the reminder

- **Own collection and routes**, so the two lists never share rows, tokens or links. A banner link cannot touch a
  reminder row and the other way round (tested).
- **Fields kept per address:** `email` (lower case), `name`, `city`, `pride`, `unsure`, `note`, `status`, `locale`,
  `consent_at`, `consent_version` (`2026-11-13`), timestamps and the hashes of the confirmation token (one, 7 days)
  and unsubscribe tokens (up to six). No IP address, user agent or phone number. Limits: name 60, city 80, Pride 120,
  note 500 characters; control characters are removed, unknown fields are refused, the body is at most 8 KiB.
- **A repeat signup keeps the first answers.** A pending address may get its confirmation again (15 minutes apart,
  at most three); a confirmed one is left alone. The answer is the same 202 text in every case, so the page never
  says whether an address was registered. The already-registered mail is not different from the first one either:
  there is only one mail type, the confirmation, and it is queued only while the row is pending.
- **No free text in any mail.** The confirmation never repeats the name or the note: the address may belong to
  someone else, and the text would reach them under our name.
- **No bulk send.** The only mail is the confirmation. Contacting carriers happens by hand from the export, and
  each person agrees the details with us.
- **Retention:** unconfirmed signups are deleted after 14 days. Everything is deleted from **31.10.2027**, after
  the Pride season, unless a row carries a later `retain_until`, which only a new explicit consent may set. Nothing
  sets it today. On request or through any mail link: immediately. The date is the one decision for the maintainer
  to adjust (`PURGE_AFTER` in `pride_banner_volunteers.py`, and the dates in the privacy notice and the consent
  text).

## Switches (all off by default)

| Switch | Where | Effect |
| --- | --- | --- |
| `PRIDE_BANNER_SIGNUP: true` in `config.yaml` (needs `GO_SUBMIT_ENABLED`) | deploy writes `PRIDE_BANNER_SIGNUP_ENABLED=true` for the Go API | the routes exist. Without the unique index the Go API keeps them off and logs why |
| `PRIDE_BANNER_MAILS_ENABLED` | Flask scheduler environment | confirmation mails are queued |
| `volunteer_form` in `mielenosoitukset_fi/utils/data/pride_banner.json` | built into the React app | the call and the form appear on the page |
| Apache rule in `deploy/apache/react-ssr-routing.conf` | host | sends the three routes to the Go API |

## Activation (needs the maintainer's go; nothing here was done in production)

1. Backup of the database (core dump) and `config.yaml`.
2. Index, with the go for production: `python -m mielenosoitukset_fi.scripts.ensure_pride_banner_indexes`.
   Revert: `db.pride_banner_volunteers.dropIndex("email_unique")` (the Go routes switch themselves off at the next start).
3. Flask: set `PRIDE_BANNER_MAILS_ENABLED`, restart the scheduler. Sign up with a test address first and check the mail.
4. Apache: install the routing rule from `react-ssr-routing.conf` (not during a deploy of other rules) and reload.
5. Go: `PRIDE_BANNER_SIGNUP: true` in `config.yaml`, deploy, restart the API (not during a backup dump).
6. React: set `volunteer_form` to `true`, build and deploy. Check as a visitor: signup, mail, confirm, removal, in both themes.

## Revert

Set `volunteer_form` back to `false` (the form disappears), remove `PRIDE_BANNER_SIGNUP` from `config.yaml` and
redeploy (the routes answer 404), unset the Flask flag, remove the Apache rule, and delete the data with the purge
command or `db.pride_banner_volunteers.drop()`. `git revert` of the PR needs no data migration.

## Limits

- The signup is rate limited per visitor (the reminder's limits) and per address. Past the per-address limit the
  answer stays the same and nothing is stored.
- A confirmed carrier who signs up again with new answers is not updated; they remove their data and sign up again.
- The mail text is Finnish only.
- The routes share the Go API with the public site; mail delivery shares the queue with the other mails.
- Contacting carriers is manual and the mail has no removal link. The privacy notice says a carrier can also ask for removal by replying, so every manual contact mail must say so ("Voit pyytää tietojesi poistoa vastaamalla tähän viestiin") and the request must be handled by deleting the row.
- No admin screen: the maintainers read the signups with the export command.
