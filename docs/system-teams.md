# Protected administration teams

Maintainer-approved direction: ordinary organization documents selected by
`NATIONAL_ADMIN_ORG_ID` and `BOARD_ORG_ID`, with protected membership semantics.
Only the governance approval workflow may enroll members. Ordinary invitations,
membership writes, removals and organization deletion must not change these
teams, including when initiated by a super admin.

New national super-admin membership requires two distinct current board votes.
New board membership requires every member of the board roster captured when
the request starts. No self-votes; duplicate votes do not increase the count.
A board-roster change invalidates a pending board request rather than shrinking
its quorum. Zero board members cannot approve anything. Existing super-admin
accounts keep their existing rights; initial bootstrap is restricted to the
explicitly named existing accounts `olivia` and `tikrutre`.

Reuse the board-clearance registry and private governance UI. New grants derive
from approved membership on user load, never by persisting inherited flags on a
profile save. Promotion through older role-edit routes must obey the same quorum.
Membership/configuration lookup failures never grant privileges. Membership
changes, votes, activation and revocation are auditable.

National moderation notifications resolve confirmed active members of the
configured national organization, not a shared support mailbox. Send one
personalized message per recipient, with unique registered links. Store intended
recipient identity on the private token registry and preserve the signed-in
actor separately when a link is used. Anonymous bearer use is described as use
of a link sent to a recipient, not verified login by that person. Existing
signed links remain valid under their original expiry and single-use rules.

Rollout requires focused authorization/notification tests and independent visual
acceptance for governance/case/email screens. Provision the two ordinary
organizations and their two approved initial members idempotently; keep config
backups and a receipt. Do not send new live test emails without authorization.

## God enrollment and login

The initial owner is Olivia's regular account, selected by
`OVERRIDE_OLIVIA_USER_ID`, never a mutable display name. The separate account is
`godolivia`, with the maintainer-supplied unique email. Do not store that real
address in source code or fixtures. The provisioning command creates an inactive,
unconfirmed ordinary-role candidate with an unusable password sentinel. It sends
no mail and does not assign a god role. It does not reset existing credentials.

`GET /auth/god` is a React-only, noindex, no-store screen with analytics disabled.
Its JSON actions extend the existing `POST /users/auth/login`; authentication and
mail delivery remain owned by Flask. Exact configured Origin and browser-session
CSRF are mandatory. `GOD_AUTH_ORIGIN` defaults to the primary HTTPS origin.
Email links use URL fragments, so their bearer tokens do not enter HTTP access
logs or referrers; an explicit POST in the original browser consumes them.
The primary production origin also accepts the existing HTTPS www hostname;
email links retain the initiating approved hostname and its browser session.

Initial enrollment requires the regular owner's fresh password and authenticator
code, followed by the new account's email link, a UV-required WebAuthn registration,
two new TOTP secrets with proof codes, a 32+ character main password and a distinct
64+ character secret. Hash both passwords with the existing Werkzeug format.
Store TOTP secrets only in the existing private MFA store and short-lived setup
proof. The application can require separate enrollments, but cannot prove the
owner installed the two TOTP secrets on physically independent devices. The owner
must do so. Do not enroll or select passwords on the owner's behalf.

Enrollment never logs the candidate in. Activation requires both completed
enrollment and unanimous appointment consent from all existing super admins,
board members and god accounts, in either order. Overlapping roles count as one
distinct account, and the candidate cannot vote for itself. The first appointment
has no existing god voters, but still requires all super admins and board members,
including the existing minimum of two board approvals. Inactive or banned
approvers remain in the roster; disabling accounts must not shrink the quorum.
God voters must complete a fresh full login within five minutes. Membership or
role changes start a new approval request without inherited votes. Activation
rechecks the live roster, so old consent cannot authorize a changed electorate.
The ordinary Olivia-plus-god override and two-person national approval do not
replace appointment consent. An enrolled candidate cannot use
initial setup to replace factors. Recovery of lost god factors requires an
explicit, audited offline procedure; ordinary password reset alone does not
produce a valid god login or bypass the remaining factors.

Every god login requires, in order: 32+ character main password, first TOTP,
email code, UV-required passkey, second TOTP, email link, distinct 64+ character
secret. Challenges expire after 15 minutes; five failed checks lock a pending
flow. Start attempts are bounded per trusted client IP and account. TOTP counters
are consumed atomically to reject replay. The final receipt lasts 30 minutes,
is bound to the browser, user and credential fingerprint, and is checked on every
Flask-Login load. Password, email, authenticator or passkey changes invalidate it.
Password/passkey shortcuts and remembered cookies cannot authenticate god users.
God accounts cannot create or use bearer API tokens as a login shortcut. Intake
activation revokes any old candidate tokens. The existing authenticated API token
validator checks the owner's role; public Go reads do not use this validator.
Email failure requires restarting the bounded flow; queued delayed messages do
not extend challenge expiry. There is no weaker fallback.

An override requires approvals from the configured regular Olivia account and a
different god account within ten minutes. The god receipt must be at most five
minutes old. Record both identities. Neither account may approve itself. Since
Olivia owns both accounts, this is two-account confirmation, not independent
human approval. Disabling a board member's account never shrinks the board roster.

## Provisioning and rollback

Emergency appointment is not enabled by the ordinary joint-override endpoint.
The maintainer's chosen rule is either:

- two distinct current board members approve the named request, or
- a registered USB-key signature is supplied together with a fresh complete god
  login (receipt at most five minutes old).

Neither branch may bypass the nominee's security enrollment. Each request binds
the target account, credential version, current board roster, reason and a
single-use challenge to a fifteen-minute expiry. A roster, credential or expiry
change invalidates the request. The panel only signs a launch ticket; it never
approves an appointment and never receives passwords, authenticator codes or
private USB keys. Signing clients talk only to the production HTTPS origin.

The `panel.lan` button is deployed as a small extension to the existing homelab
status panel on `192.168.1.112:8090` (proxied as `http://panel.lan`). It is
reachable only after the panel passphrase has been entered, requires a
same-origin POST with a CSRF token, and refuses to sign while `enabled` is not
`true`. Its Ed25519 private key lives at
`/etc/moso-emergency-panel/private.pem` (root-only, 0600); the panel public key
must be registered in `GOD_EMERGENCY_PANEL_KEYS` before activation. The current
panel key ID is `edcb7ae6c355e23ac52e7a2ce81266fa05b12d91f771d08fd619a3210ace00d9`.

The attached `VAULT-KEY-A` also contains an unrelated SessionVault key. It was
left untouched. A separate encrypted appointment key
(`mielenosoitukset-god-emergency-v1.encrypted.pem`) now exists on the same
volume; its public key ID is
`720a7c26b97024b16152fe6123a16403bb5f1e0c86e41b879d83175abaf84ca1`. Only the
owner knows the password; it is not stored in the repository, chat or the
application. The Mac-side signer verifies the mounted device and never uploads
the private key. An ordinary USB key is copyable and is not equivalent to a
non-exportable hardware authenticator; losing the password or the drive
requires the offline recovery procedure.

Both trust anchors stay inactive until the protected application code is
deployed and `GOD_EMERGENCY_ENABLED`, `GOD_EMERGENCY_PANEL_KEYS` and
`GOD_EMERGENCY_USB_KEYS` are configured. Removing those values, or setting
`GOD_EMERGENCY_ENABLED=false`, disables the emergency path without changing
existing accounts.

To revoke the panel key, delete it from `GOD_EMERGENCY_PANEL_KEYS` and remove
`/etc/moso-emergency-panel/private.pem`; to revoke the USB key, delete its entry
from `GOD_EMERGENCY_USB_KEYS`. Existing approvals that used a revoked key fail
the activation recheck.

Deploy and verify protections before configuring or seeding memberships. Use
`scripts/provision_system_teams.py` first without `--apply`, supplying deliberate
distinct organization IDs, the two verified existing user IDs, and the approved
new account username/email. Run with `--apply` only against the intended database;
retain its non-secret receipt. It checks identity collisions and is idempotent.
Back up production configuration privately, add the three returned config values,
restart Flask, then apply bootstrap. The apply command rejects mismatched config
IDs. Verify protected organization edits are denied and recipient
resolution returns exactly the intended active members. No indexes or ordinary
account roles are changed by bootstrap. The owner begins enrollment from the
React screen only after it is deployed, using the ordinary account first.

Do not roll back to code that ignores the protections while team memberships or
god sessions remain in use. First disable the candidate/god account, invalidate
its challenge receipts, and remove governance-managed grants through an audited
maintenance action. Existing legacy administrator roles are preserved; removing
these config values alone is not a safe way to grant or revoke privileges.
