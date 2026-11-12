# Token and approval lifecycle (SEC-04)

Inventory taken from the code on 12 November 2026. "Tested" names the test in
`tests/test_token_lifecycle.py` unless another file is given.

| Flow | Token | Expiry | Revocation | Replay | Double decision |
| --- | --- | --- | --- | --- | --- |
| Demonstration approve / reject / preview links (`admin_demo_bp`) | Signed itsdangerous string plus a `magic_links` registry row keyed by SHA-256 hash; forged or unregistered strings are refused | 24 hours (signature) and `expires_at` in the row → 410 | `revoked` flag, security-case suspension, and every terminal decision revokes sibling preview/approve/reject/edit links | Single use: `used_at` set after the decision, later use shows "already used" (200) and is audited; bound to the first IP | `apply_demo_decision` is idempotent: same decision reuses its id, no repeated notification, history or audit. Opposite decisions: last one wins (existing behaviour) |
| Demonstration edit link | Same registry, action `edit` | 1 h, 24 h or 7 d chosen at creation → refused when expired | Revocable from the token admin; revoked on terminal decision | Reusable until it expires or is revoked (it is an edit session, not a one-shot) | n/a |
| Organizer cancellation link (`/cancel_demonstration/<token>`) | Random token, hash stored in `demo_cancellation_tokens` | `expires_at` (`TOKEN_EXPIRY_DAYS` after creation) | None besides expiry. Not revoked when the demo is cancelled by other means | `used_at` set after the action; later use refused. The check and the mark are two separate steps, so two simultaneous POSTs can both pass (see Questions) | Not verified here |
| Password reset (`/password_reset/<token>`) | Signed JWT carrying the e-mail address | 1 hour | None. Existing sessions and older reset links stay valid after a reset | Single use through `used_password_change_tokens`, recorded after the password change; the token itself is stored there in plain text | n/a |
| E-mail confirmation (`/confirm_email/<token>`) | Signed JWT carrying the e-mail address | 1 hour | None | Reusable until expiry, harmless: it only sets `confirmed: true` | Idempotent |
| Campaign volunteer confirmation (`/kampanja/confirm/<token>`) | Random token stored in `volunteers` | 24 hours | Token fields removed on consume | Consumed: second use returns 400 | Idempotent |
| Organization invites | No token. An e-mail entry in `organizations.invitations` matched against the signed-in user's e-mail | None | Decline or accept removes the entry | Accept removes the entry first, so a second accept answers "invite not found" | Second accept cannot add the member again |
| Case approvals (`approve_cancellation`) | Admin session with `EDIT_CASE` | n/a | n/a | n/a | Already cancelled demo returns `already_cancelled` without cancelling again or rewriting the case |
| Suggestion approvals (`/suggestions/<id>/apply`, `/status`) | Admin session with `EDIT_DEMO` | n/a | n/a | An applied suggestion can be applied again; every apply writes its own edit history | Reject/close after apply overwrites the status (no guard) |

## Changed in this work

- Password reset and e-mail confirmation tokens were identical in shape, so a
  confirmation link e-mailed to an address was also a valid password reset
  link for it, and the other way round. New tokens carry a `purpose` claim and
  each verifier refuses the other purpose. Tokens issued before this change
  carry no claim and keep working until their hour is up, so no pending mail
  breaks. Revert: remove the `purpose` checks in `utils/auth.py`.

## Covered by regression tests

Cancellation link single use, expiry and unknown token; magic link expiry
(410), revocation (403), forged and unregistered signature, wrong action, and
approval replay; reset token single use, expiry and garbage; purpose
separation and legacy tokens; confirmation expiry and replay; volunteer
confirmation consume and expiry. Decision idempotency and sibling revocation
are covered in `tests/test_demo_decision_service.py`.

## Questions (not changed here)

1. Should a password reset end the user's other sessions and invalidate other
   outstanding reset links? Suggested: yes, by storing a `password_changed_at`
   and rejecting sessions and reset tokens issued before it. This changes
   session semantics and needs a schema field, so it waits for approval.
2. Should reset tokens be stored hashed in `used_password_change_tokens`?
   Suggested: yes; a database read currently reveals spent tokens (spent only,
   so low risk). Needs a one-off migration of existing rows.
3. Should the cancellation and reset consume steps become an atomic claim
   (`find_one_and_update` on `used_at: None`) before acting, with a rollback on
   failure? Suggested: yes for cancellation; it reorders the flow, so it should
   be reviewed. A unique index on the reset-token record would also fix the
   reset race and is a schema change.
4. Should an applied suggestion refuse a second apply, and a rejected one
   refuse apply? Suggested: yes, but admins may rely on re-applying other
   fields today.
5. Should organization invites expire? Suggested: 30 days, which needs an
   `invited_at` on each invitation (schema).

Related: incident #912/#913 protections (SEC-05) were not touched by this work.
