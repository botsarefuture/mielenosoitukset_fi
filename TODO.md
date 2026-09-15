# TODO — active task list

Consolidated list of fixes/features requested (so none are forgotten). Tick items off as they land.

## Overflow fixes

- [x] Ensure no overflow on public pages (reported for `/city/helsinki/tanaan`, cities pages)
  - [x] Header `.container` overflows viewport by 24–64px on the right (clips bell/user area)
  - [x] Header `.branding` pokes ~9px past viewport on mobile
  - [x] `.city-card` overflows ~6px past viewport on `/cities` at ~360px
- [x] Verify no horizontal page scroll / protruding elements on home, cities, city today pages at desktop + mobile widths
  - Verified via Playwright + Jinja harness at 320/360/390/768/1024/1440 (zero right-side offenders); live-site header also measured.

## Fixes
- [x] Please ensure hero consistency between all the user facing pages!

## Features

- [x] Add an info/welcome email to people who sign up as translators
- [x] Allow all logged-in users to access the admin dashboard, but only show modules relevant to their role/job
- [x] On demo detail pages, hide the "Seuraa" (follow) button for organizations that cannot be followed
- [x] Ensure that the user can enable 2fa in their settings!

## Audit logging and GDPR

- [ ] Build a complete, reliable and mutually compatible audit logging system across the whole service
  - [ ] Define one versioned canonical event schema for `admin_logs`, `super_audit_logs`, `demo_audit_logs`, `login_logs`, `board_audit_logs` and future audit sources
  - [ ] Include stable event, actor, subject/entity, timestamp, outcome, source, request and `correlation_id` fields so one investigation can be followed across every log source
  - [ ] Add adapters and migration coverage for legacy entries; document which fields may be absent and guarantee that mixed old/new data remains searchable
  - [ ] Audit every security- or privacy-relevant read and write, including log access itself, permission changes, exports, deletions, authentication attempts and automated/background actions
  - [ ] Make audit writes failure-aware and observable: retries or a durable queue, delivery/error metrics and alerts must prevent silent gaps
  - [ ] Use UTC timestamps, deterministic ordering and tamper-evident/append-only storage controls with documented administrator access
  - [ ] Provide one investigation UI with cross-source search, actor/entity links, surrounding events, correlation navigation and appropriately permission-gated technical details
  - [ ] Apply field allowlists and centralized secret redaction before persistence where possible; never store passwords, credentials, authorization headers, session cookies or raw tokens
  - [ ] Define and enforce per-log retention, deletion/anonymization and backup policies based on purpose, legal basis and data-minimization requirements
  - [ ] Document data-subject access/export workflows, access auditing, incident procedures, controller/processor responsibilities and relevant data flows
  - [ ] Add automated completeness, authorization, redaction, retention, migration and cross-source correlation tests, plus periodic production audit sampling
  - [ ] Complete and record a GDPR/privacy review with the responsible privacy or legal owner; technical tests alone must not be treated as proof of full legal compliance

## Process

- [x] Update CHANGELOG.md for every user-facing change
