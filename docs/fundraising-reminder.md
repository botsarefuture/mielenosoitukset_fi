# Fundraising opening reminder

Status: implemented behind switches that are all off, 13 November 2026. Not active in production.
Collecting the addresses and sending the mails was approved by the maintainer on 13 November 2026.
The first real bulk send, the production index and the switches each need the maintainer's go
in the working session (see "Activation").

## What it does

A visitor of `/keräys` can give an e-mail address before the collection opens (16.11.2026 00:00
Europe/Helsinki). They confirm it from a link, and get **one** reminder when the collection opens.
An optional, unticked checkbox ("Haluan myös kuulla keräyksen tuloksista") is stored as a separate
consent flag. Nothing implemented sends anything for it; a results message would need its own decision.

## Parts

| Part | Where | Notes |
| --- | --- | --- |
| Signup, confirm, remove routes | Go, `go-api/fundraising_reminder.go` | `POST /api/fundraising/reminder`, `…/confirm`, `…/unsubscribe` |
| Form and link page | React, `FundraisingReminder.tsx`, `fundraising-reminder.ts` | Form in the pre-launch card; `/keräys?muistutus=vahvista#t=…` and `…=peru#t=…` show a single button |
| Token minting and all mail | Flask, `utils/fundraising_reminder.py` and three jobs | Go has no mail sender; mail goes through `email_queue` |
| Data | collection `fundraising_reminders`, markers in `fundraising_reminder_sent` | unique index on `email` |
| Retention | job `purge_fundraising_reminders` and the same module's `purge` | also a command with `--dry-run` |

## Data kept per address

`email` (lower case), `status` (`pending`/`confirmed`), `locale`, `results_consent`, `consent_at`,
`consent_version` (the consent text version, `2026-11-13`), `created_at`, send and claim timestamps,
hashes of the confirmation token (one, with `confirm_expires_at`) and of the unsubscribe tokens (up to six,
one per mail). No IP address, user agent or name is stored. The per-IP rate limit counter uses an HMAC of the
address in the existing `demo_submission_tokens` rate buckets, which expire as before.

## Flow and guards

1. **Signup.** Same-origin only (`Sec-Fetch-Site` not `cross-site`, `Origin` equal to the configured site),
   `application/json` up to 2 KiB, unknown fields refused. There is no session, so there is no CSRF token
   to check; the origin check is the guard. Honeypot field `website`: if filled the answer is the normal 202
   and nothing is stored. Email: plain ASCII address up to 254 characters, no display name. Consent is required.
   Rate limit: per IP 5 per minute and 20 per hour (429); per address 2 per minute and 4 per hour, where
   going over gives the normal 202 and stores nothing. The panic switch answers 503 like the other write routes.
2. **Idempotent and silent.** A new address gets a pending row; a repeat does not create a duplicate. A pending
   row may get the confirmation again (15 minutes apart, at most three). A confirmed one is left alone. The
   answer is the same 202 text in every case, so it never says whether an address is registered. (A wrong
   address format is a 400, which says nothing about registration.)
3. **Confirmation mail** (Flask job, every 2 minutes). The job claims the row atomically, mints a random token
   (32 bytes), stores its SHA-256 hash with a 7-day expiry, and queues a plain-text mail. Raw tokens are only in
   the mail. Confirm is one atomic step that checks the hash and expiry and consumes the token, so a link works
   once. Expired or used links say so and point to the form.
4. **Reminder** (Flask job, every 5 minutes, but only inside the send window). See "Never twice".
5. **Remove.** Every mail has a link to `/keräys?muistutus=peru#t=…` (one button, no action on page load, so mail
   scanners that prefetch links do nothing) and `List-Unsubscribe` plus `List-Unsubscribe-Post` headers for
   one-click removal by the mail client. Both delete the row. Removing twice answers the same. The unsubscribe
   routes do not need an `Origin` (mail clients send none); the token is the authorisation.
6. **Tokens** follow [token-lifecycle.md](token-lifecycle.md): random, only hashes stored, expiry for the
   confirmation, single use, atomic consume. Unsubscribe tokens have no expiry (they must work until the data is
   deleted) and are consumed by the deletion itself. The token is in the URL fragment so it is not sent to the
   server in a page request, logged, or leaked through the referrer.

## Never twice

- `send_reminders` runs only inside 16.11.2026 00:00–17.11.2026 00:00 Helsinki, when
  `FUNDRAISING_REMINDER_MAILS_ENABLED` and `FUNDRAISING_REMINDER_BULK_SEND_APPROVED` are both set.
- Each row is claimed atomically (`reminder_claimed_at`) before anything is queued.
- A marker keyed by the hash of the address is inserted first, so even two rows for one address (for example
  without the unique index) send once, and a drained queue cannot cause a second send.
- The queue job has a fixed `_id` per row.
- A crash between the claim and the queue insert loses that one mail rather than risking a duplicate. The dry run
  reports `claimed_never_queued` to find them.
- Failed queue inserts roll the claim and marker back.

**Dry run** (sends nothing, ignores the flags and the window):

```bash
python -m mielenosoitukset_fi.scripts.send_fundraising_reminders --dry-run
```

It prints `would_send`, `confirmed_total`, `pending`, `already_claimed` and `claimed_never_queued`.

## Retention

- Unconfirmed signups: deleted 14 days after creation (7-day link plus a week).
- Everything, including the send markers: deleted from 17.3.2027, 30 days after the collection ends on 15.2.2027.
  A row may carry `retain_until` (reserved for a later explicit consent); the purge skips such rows until that
  date. Nothing sets it today.
- On request or through any mail link: immediately.
- Job `purge_fundraising_reminders` runs daily and needs no flag, because deleting is the safe direction.
  Command with a preview: `python -m mielenosoitukset_fi.scripts.purge_fundraising_reminders --dry-run`.

## Switches (all off by default)

| Switch | Where | Effect |
| --- | --- | --- |
| `FUNDRAISING_REMINDER: true` in `config.yaml` (needs `GO_SUBMIT_ENABLED`) | deploy writes `FUNDRAISING_REMINDER_ENABLED=true` for the Go API | the routes exist and the details answer carries `reminder_signup: true`, which shows the form. Without the unique index the Go API keeps the routes off and logs why |
| `FUNDRAISING_REMINDER_MAILS_ENABLED` | Flask scheduler environment | confirmation mails are queued |
| `FUNDRAISING_REMINDER_BULK_SEND_APPROVED` | Flask scheduler environment | the opening reminder may be queued. Set only on the maintainer's go |
| `FUNDRAISING_REMINDER_BASE_URL` | Flask scheduler environment | link base, default `https://mielenosoitukset.fi` |

## Activation (needs the maintainer's go; nothing here was done in production)

1. Backup of the database (core dump), and `config.yaml`.
2. Index, with the go for production: `python -m mielenosoitukset_fi.scripts.ensure_fundraising_reminder_indexes`.
   Revert: `db.fundraising_reminders.dropIndex("email_unique")` (the Go routes then switch themselves off at the next start).
3. Flask: set `FUNDRAISING_REMINDER_MAILS_ENABLED`, restart the scheduler. Send one confirmation to a test address first.
4. Go: `FUNDRAISING_REMINDER: true` in `config.yaml`, deploy, restart the API (not during a backup dump).
5. Before 16.11.2026: dry run, maintainer's go, then set `FUNDRAISING_REMINDER_BULK_SEND_APPROVED`.
6. After 16.11.2026 and the send: unset the approval flag.

## Revert

Remove `FUNDRAISING_REMINDER` from `config.yaml` and redeploy (the form disappears, the routes answer 404), unset
the Flask flags, and delete the data with the purge command or `db.fundraising_reminders.drop()` and
`db.fundraising_reminder_sent.drop()`. `git revert` of the PR needs no data migration.

## Not done / limits

- The results message for the optional checkbox is not implemented.
- The rate limit rides on the existing `demo_submission_tokens` buckets (database), so it works across Go instances.
- The mail text is Finnish only.
- Mail delivery goes through the shared queue: a stuck queue delays both mails; the opening reminder then arrives late
  but the window only controls queueing, not delivery.
