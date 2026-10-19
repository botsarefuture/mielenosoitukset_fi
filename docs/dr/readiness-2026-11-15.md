# Recovery readiness deadline: 15 November 2026

The owner set this deadline on 19 October and expects hostile activity from
1 December or earlier. This is the owner's threat-planning assumption, not an
independently confirmed incident or attribution. Complete rehearsal before the
deadline and keep the remaining time for fixes and retesting.

## Required outcome

One authenticated recovery action must create a working replacement from trusted
release, DB and media artifacts, run functional checks, and show progress and
evidence. Public traffic cutover is a separate explicit action. Rehearsals capture
email locally and cannot contact production services or process historical jobs.
The temporary static view supports public reading while full recovery runs.

The existing pentest host proves application recovery, not a production-identical
or blank-host deployment. It runs the same deployed app commit and MinIO binary,
Python 3.12 on Ubuntu 24.04.4, but nginx replaces Apache, Gunicorn differs, the
worker count is smaller, and several background integrations are disabled.

## Acceptance evidence

| Capability | Current evidence | Required before deadline |
| --- | --- | --- |
| Public pages, event API and media | Working copy; anonymous HTTP checks; full media restored | Browse/search/filter/calendar/detail tests with backend-independent browser assets |
| Accounts and administration | Global admin login; admin creation of synthetic user and captured credential email | Registration, recovery, role restrictions, edits, moderation and organization workflows |
| Event writes/uploads | Restored app and local MinIO | Create/edit/approve event, upload and read image, recurring-event behavior |
| Email/queues | New messages captured; historical jobs quarantined | Queue retries and restart persistence; deliberate cutover to delivery only when authorized |
| Dependencies | Local MongoDB, Redis, MinIO and SMTP capture running | Consistent, versioned DB/media/release artifacts and offline browser dependencies |
| Fresh-host provisioning | Not yet proven | Automated OS/runtime/services/TLS setup and a measured empty-host rehearsal |
| Production parity | Differences recorded above | Capture and review production service/package/config inventory; test parity rather than claim image identity |
| Recovery control | Prepared-host app+DB rehearsal command exists | Authenticated background job, progress, durable audit, concurrency lock and clear failure/cleanup behavior |
| Traffic cutover | Sandbox snapshot switch measured | Staged production routing plan, health gates, rollback and explicit operator promotion |
| Independent copies | Existing pentest box and private artifacts | At least two independent provider/account locations with tested restore access |

## High-risk snapshot profile

A 15-minute generation interval is a proposed high-risk mode, not an enabled
schedule. A successful capture can still be older than 15 minutes by the time
generation, distribution and verification complete. Track actual data age and
the last successful publish independently from scheduler success.

Use public content only, bounded incremental fetches, no overlapping runs, hash
manifests, verified staged uploads and atomic promotion. Keep multiple previous
good versions. A failed, empty or compromised-source capture must not replace
the last known good release. Mirroring is not a substitute for versioned backups.

Choose distinct failure domains: providers, accounts, regions, DNS/control access
and recovery credentials. Geographic placement alone does not prevent attacks.
An Israeli location is not intrinsically immune. Select locations for measured
availability, independent operations and reachability rather than that assumption.
No new international servers, paid services or recurring schedules were created
by documenting this proposal.

## Delivery order

1. Finish and verify the usable static snapshot and fix current application issues.
2. Package complete recovery artifacts and a reviewed environment/config contract.
3. Build the recovery job and operator control; keep promotion separate.
4. Prove fresh-host recovery and the functional matrix using capture-only email.
5. Add and test independent copies and the opt-in high-risk snapshot profile.
6. Complete an operator-led outage rehearsal and close evidence gaps by 15 November.

Prepared-host measurements (103 seconds app+DB, separate 204 seconds media) are
useful baselines. They are not end-to-end production RTO or an RPO guarantee.
