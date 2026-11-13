# City admin applications, trust and local teams: proposal

Status: proposal for the maintainer, 11 November 2026. Nothing here is implemented
yet. Items marked *(approval)* touch permissions, schema, personal data or real
email and need an explicit go-ahead.

## 1. What exists today (verified)

**Roles and grants**
- A city admin has `role: "city_admin"` on the user and one document in
  `admin_scope_grants` (`scope_type: "city"`, `scope_keys`, `permissions`,
  `role: "city_reviewer"`, `revoked_at`)
  (`admin/admin_user_bp.py:279-345`).
- Only global admins can grant or change them
  (`_can_manage_scope_grants`, `admin_user_bp.py:233`).
- **Grantable permissions** (`admin_user_bp.py:220-230`): `LIST_DEMOS`,
  `VIEW_DEMO`, `EDIT_DEMO`, `ACCEPT_DEMO` (publish), `CREATE_DEMO`,
  `GENERATE_EDIT_LINK`, and optionally `LIST_CASES`, `VIEW_CASE` and `EDIT_CASE`.
- **Implicit permissions:** every city admin also gets organization
  permissions without them being listed in the grant (`LIST/VIEW/CREATE/EDIT_ORGANIZATION`,
  `INVITE_TO_ORGANIZATION`; `users/models.py:25-31, 561-569`).
- **Revoking and auditing:** a grant is revoked by setting `revoked_at`, and
  every grant change is written to the user history (`PENDING_HISTORY`,
  `flush_user_history`).
- **City picker:** saving a grant for a city that is not enabled enables it
  automatically (`_auto_activate_granted_cities`). The create and edit forms
  list all 309 catalog cities, marking disabled ones "(ei käytössä)", so a city
  no longer has to be enabled by hand first.
- **Notifications:** pending events notify the reviewers of their city in the
  site inbox (`utils/notifications.py:notify_city_reviewers`). Urgent ones also
  go to Telegram through the outbox (#964). Reviewers have a deadline
  dashboard (#968).

**Production (read-only, 11 Nov 2026)**
- 4 users have the `city_admin` role.
- There are 8 active city grants: Helsinki ×3, Sastamala, Ylöjärvi, Äänekoski,
  Joensuu and Brändö.
- No city admin has a case permission.
- 31 cities are enabled. Several, for example Tampere and Turku, were enabled
  by hand under the old workaround and have no admin.

**Workflows to reuse**
- **Cases** (`cases` collection, admin `/admin/case/`) already carry a type,
  history, notes, replies, an action log, handler notifications and
  city-scoped access. Case scope today comes only from a linked demonstration
  (`utils/case_access.py:case_scope_query`).
- **Developer scope requests** (`developer_bp.py:98`, `admin_dev_bp.py`) are a
  minimal "request → pending → approve/deny" flow. Their admin email address
  is hard-coded.
- **Board and national team clearance** (`utils/team_governance.py`) uses
  quorum votes. That is far heavier than a city role needs, so it is not
  proposed here.
- **Profiles** have `displayname`, `bio` and a profile picture. There are no
  structured activism fields.

## 2. Principles

1. **Local and proportionate.** City admins moderate events in their area.
   They are not national admins, so trust should come from the local scene and
   a human check, not from identity documents.
2. **Least privilege first, more later.** Start with what moderation needs;
   add organization editing and edit-link generation deliberately.
3. **Teams, not individuals.** At least two admins per city is the target,
   shown and encouraged, never enforced.
4. **One workflow.** Applications are cases, so handling, history, notes,
   replies and notifications already exist and are familiar to admins.
5. **Minimum personal data.** Ask only what helps decide, keep it visible only
   to the people who decide, and delete rejected applications after a set time.

## 3. Proposed user flow

### Where people find it
- **City page** `/city/<city>`: a short block whose text depends on how many
  active admins the city has.
  - 0 admins: "Paikkakunnalla ei vielä ole kaupunkiadminia. Haluatko auttaa?"
  - 1 admin: "Paikkakunnalle haetaan toista kaupunkiadminia."
  - 2 or more: nothing, or a quiet link.
- **`/cities`:** the same status as a small marker per city, plus a sentence in
  the intro, so recruiting is visible where people browse.
- **A general page**, for example `/kaupunkiadmin`: what the role involves (time,
  responsibilities, what admins can and cannot do), then the form.

### Who can apply
- A signed-in user with a confirmed email. The role needs an account anyway,
  and this needs no new identity checks.
- More than one person can apply for the same city, and one person can apply
  for several cities.

### The form (short, one page)
- **Cities to help with:** multiple choice, prefilled from the city page they
  came from.
- **About you:** who you are and why you want the role (free text, required,
  bounded length).
- **Activism involvement:**
  - cities you are active in (multiple choice);
  - groups or organizations, as free text and optionally linked to existing
    organizations on the site; none is a valid answer;
  - experience organizing demonstrations or events: none, some or a lot, with
    a short description.
- **References (optional):** one or two people already active locally or on
  the site who can vouch, with a username or contact. "No references" is a
  valid choice and never blocks the application.
- **Consent:** how the application is handled and stored, required. Nothing
  else is required: no ID, phone number or address.

### What happens after sending
- A case of type `city_admin_application` is created with `city_keys`. The
  applicant sees a confirmation and can see the status (received, in review,
  approved or declined) on their own account page.
- Global admins are notified in the site inbox, and by email when urgent mail
  is approved for this. Existing admins of the same cities can **read and
  comment** on the case so the local team can vouch, but cannot decide.
- **Small code change:** `case_scope_query` gains a branch for application
  cases matched by `city_keys`. Demo-linked scope is unchanged.

## 4. Review and trust model (proportionate)

**Decision:** a global admin approves or declines, as today. That is the only
role allowed to grant city scope, and it stays that way.

**Checklist** in the case, as guidance and not a scored test:
1. **Account:** the email is confirmed and the account is not new or empty.
   Age alone never decides.
2. **Local connection:** shown by the involvement answers, a reference, an
   existing local admin vouching, or a linked organization on the site.
3. **A short conversation:** a call or video chat with a global admin or an
   existing city admin. It is the strongest proportionate check and is
   required for the **first** admin of a city, where no local team can vouch.
4. **References:** if given, contact at least one.
5. **Conflicts:** note any obvious conflict of interest, such as wanting to
   moderate only their own group's events.

**Not proposed:** ID documents, strong electronic identification, background
checks or quorum votes. The data risk and the barrier would be out of
proportion to what a city admin can do.

**On approval:** grant city scope with the starter permissions (section 5),
send an inbox welcome with the role guide and their city team, and record the
approval in the case and the user history.

**On decline:** a short, kind message with a reason category. The applicant
can apply again later.

## 5. Permissions: start small *(approval)*

Proposed tiers, implemented as presets in the existing grant editor:

| Tier | Permissions | When |
| --- | --- | --- |
| Starter | `LIST_DEMOS`, `VIEW_DEMO`, `EDIT_DEMO`, `ACCEPT_DEMO`, `LIST_CASES`, `VIEW_CASE` | on approval |
| Full | + `CREATE_DEMO`, `EDIT_CASE`, `GENERATE_EDIT_LINK`, organization permissions | after about 2 months of active moderation, or immediately for a city's established team |

- Make the organization permissions **explicit** in the grant instead of
  implicit for every city admin. It is a small change in `users/models.py`.
  Existing admins keep them through a one-off migration, so nobody loses
  access silently.
- `ACCEPT_DEMO` stays in the starter tier because publishing local events is
  the core of the role. Every acceptance is already audited and can be undone.

## 6. Accountability and revoking

- **Already in place:** grants are revoked through `revoked_at`, and every grant
  change is audited.
- **Add:**
  - **Step down:** a self-service "Luovun roolista" button for an admin's own
    city grant. Other admins of the city are notified.
  - **Inactivity:** if a city admin has had no sign-in and no review for 90
    days, global admins see a flag. Nothing is revoked automatically.
  - **Yearly check:** once a year each admin confirms they want to continue.
    Silence makes them inactive in the coverage view, not revoked.
  - **Reasons:** a revocation reason (stepped down, inactive, misuse or other)
    stored in the history.
  - **Concerns:** a "report a concern about an admin" action for other admins,
    which opens a case for global admins.
- **Misuse:** revoke immediately, review that admin's recent acceptances, and
  re-check the affected events.

## 7. Activism profile

New optional profile section, edited by the user at any time, prefilled into
applications *(approval: schema and personal data)*:

- cities active in (multiple choice);
- groups and organizations, as free text and optional links to site
  organizations;
- organizing experience, as a level and short text;
- volunteer commitments, as free text.

**Visibility is per field, set by the user:**
- **Admins only** (the default): visible to global admins and the admins of
  shared cities.
- **Public:** shown on the public profile.

Applications keep a snapshot of what was submitted. The profile can change
later without rewriting the record of what was decided.

## 8. Teams of at least two

- **Coverage view for global admins:** each city with its active admin count
  (0, 1 or 2+), last activity, open applications and inactive flags, sorted so
  cities with 0–1 active admins come first. This is the main recruiting tool.
- The public city status from section 3 asks for help where a city has fewer
  than two admins.
- **City team panel** in the admin dashboard: the other admins of my cities,
  with their display names and how they prefer to be contacted (shared with
  each other only), and an optional team chat link stored in `city_settings`
  (for example a Telegram group).
- Shared work already happens through cases and the review queue. Show
  "kuka käsittelee" on pending events so two admins don't duplicate work.
- **No hard limits:** the first applicant for a city can be approved alone.
  The city then shows "haetaan toista kaupunkiadminia".
- **Nationally managed cities (maintainer, 11 November 2026):** Helsinki is
  moderated by the national admin team, not by local city admins. It has a
  very large amount of activism and a small but fragmented scene in which
  people in different organisations may not cooperate because of conflicts,
  so a local admin could not review everyone's events neutrally. Helsinki
  therefore shows "Valtakunnallinen tiimi" in the coverage view, never asks
  visitors to apply, and does not accept city admin applications. Drafts
  #1086 and #1087 hardcode the list (`helsinki`) in Flask and Go.

## 9. Data and privacy *(approval)*

- **Stored:**
  - **Application cases:** the form answers, the reviewer's notes and the
    decision.
  - **Profile fields:** whatever the user chooses to enter.
- **Retention:** approved applications are kept while the role is held, plus 12
  months. Declined or withdrawn ones are deleted after 12 months. The user can
  delete their profile fields at any time.
- **Never:** ID documents, phone numbers unless the applicant offers one for
  the call, or anything sent to analytics.
- Add this to the privacy notice (`/privacy`) before launch.

## 10. Suggested phases

1. **Phase 1, visibility (small, no new data):**
   - the coverage view for global admins;
   - "haetaan kaupunkiadminia" on city pages and `/cities`, with a link to
     contact support until the form exists.
2. **Phase 2, applications:** the application page and form, the
   `city_admin_application` case, inbox notifications, the applicant status
   view, and the `case_scope_query` branch for local admins.
3. **Phase 3, profile and tiers:**
   - the activism profile fields with per-field visibility;
   - permission presets;
   - explicit organization permissions with the migration.
4. **Phase 4, accountability:** step down, inactivity flags, yearly
   confirmation, revocation reasons and admin concern reports.

Each phase follows the existing rules: tests, a visual review for UI, the
changelog, and React for the public pages (the application page and form)
with the write handled by the backend.

## 11. Questions for the maintainer

1. Who reviews applications? All global admins, or a named group, for example
   whoever handles cities?
2. Is a short call or video chat acceptable as the standard check for a city's
   first admin?
3. Should the starter tier include `ACCEPT_DEMO`, or should a new admin's first
   acceptances need a second admin's approval?
4. Which retention periods and privacy notice wording should be used?
5. Where should applications notify? The site inbox only, or also email or
   Telegram?
6. Should the public city page show how many admins a city has, or only
   "haetaan"?
7. Should cities enabled by hand without admins stay enabled, or be disabled
   when they have no admin and no events? This affects which cities `/cities`
   shows.
8. Should the nationally managed cities list stay hardcoded, or become a
   `city_settings` flag that global admins can toggle (for example if another
   large city needs the same treatment)?

## Duplicate submissions (proposed, awaiting maintainer approval)

The Go handler checks for an open application and then inserts, so two
simultaneous submissions from one user can both pass the check. The delivery job
is not affected: the case ID equals the application ID, so each application gets
exactly one case. The harm is two open applications from one user.

**Proposed index** (not created by any code; a maintainer runs it):

```js
db.city_admin_applications.createIndex(
  { user_id: 1 },
  { unique: true, name: "city_admin_applications_one_open_per_user",
    partialFilterExpression: { status: { $in: ["received", "in_review"] } } }
)
```

It matches the existing rule of one open application per user, not per city.
Decided applications (approved, declined, withdrawn) fall out of the index, so
the user can apply again. `$in` in a partial filter needs MongoDB 6.0 or newer;
production runs MongoDB 7.0.37 (checked 2026-11-12 with `mongod --version` on lc-db), so it is supported.

**Handler behavior.** A duplicate key error on insert returns 409
`APPLY_OPEN_EXISTS`, the same code as the existing check, so the form needs no
change. Without the index nothing changes, so the code can ship before the index.

**Before creating the index.** Run `python scripts/check_city_admin_application_duplicates.py`.
It is read-only and lists users with more than one open application, which would
make index creation fail. Resolve those by hand (withdraw or decline extras) first.

**Rollback.** `db.city_admin_applications.dropIndex("city_admin_applications_one_open_per_user")`.
No data is changed by creating or dropping it. Reverting the Go change is optional;
the duplicate-key branch is then simply never reached.
