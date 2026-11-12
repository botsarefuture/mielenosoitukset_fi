# Mielenosoitukset.fi — Human-Readable Codebase Guide

This is the plain-language guide to the codebase. It is meant for humans who need to understand what this project does, how it is wired together, and where to look when something breaks.

If you only read one section, read “How a request moves through the app”.

What this project is
--------------------
Mielenosoitukset.fi is a public website for finding and submitting demonstrations in Finland. It also has an admin dashboard for moderation and an API for programmatic access.

It is built on Flask (Python) with MongoDB as the database. It has a small background job system, a mail queue, and a Socket.IO chat feature.

Where things live (map of the repo)
----------------------------------
If you are lost, start here:

- `mielenosoitukset_fi/app.py`: creates the Flask app and wires everything together.
- `mielenosoitukset_fi/basic_routes.py`: the main public site routes (home page, list, submit, detail, etc).
- `mielenosoitukset_fi/admin/`: admin dashboard routes (moderation, orgs, users, audits, background jobs).
- `mielenosoitukset_fi/api/`: JSON API routes and helpers.
- `mielenosoitukset_fi/utils/`: shared helpers (DB access, caching, auth, notifications, tokens, etc).
- `mielenosoitukset_fi/utils/classes/`: the data models (Demonstration, Organization, etc).
- `mielenosoitukset_fi/templates/`: Jinja templates (HTML pages and emails).
- `mielenosoitukset_fi/static/`: CSS, JS, fonts, images.
- `run.py`: starts the app locally.
- `run_aggregate.py`: analytics rollup service.

How a request moves through the app
-----------------------------------
Here is what typically happens when someone opens a page or submits a form:

1) A request hits a Flask route (often in `basic_routes.py` or a blueprint).
2) Flask-Login checks if the user is logged in (if needed).
3) The route reads or writes data in MongoDB (via `DatabaseManager` or a model class).
4) Business logic runs (validation, permissions, logging, notifications).
5) The response is returned (HTML template or JSON).

If you are debugging a page, start at the route and follow the data from there.

How data is stored (MongoDB)
----------------------------
The database is MongoDB. There is no SQL schema; documents are stored in collections. Here are the important ones:

- `demonstrations`: the main demo/event data.
- `recu_demos`: recurring demo series.
- `organizations`: organizer orgs.
- `users`: user accounts.
- `memberships`: user/org roles and permissions.

Other key collections:

- `demo_audit_logs`, `super_audit_logs`, `board_audit_logs`: admin/audit logging.
- `cases`: admin support cases (errors, suggestions, cancellations).
- `notifications`: in-app notifications.
- `messages`: chat messages.
- `demo_submission_tokens`: submission tokens for safety.
- `demo_submission_errors`: failed submission logs.
- `demo_notifications_queue`: notifications waiting to be sent.
- `analytics`, `d_analytics`: raw and rolled-up analytics.
- `email_queue`: queued emails.
- `api_tokens`, `api_usage`: API token auth and usage logs.

Core objects (the “models”)
---------------------------
These live in `mielenosoitukset_fi/utils/classes/` and `mielenosoitukset_fi/users/models.py`.

- `Demonstration`: a demo/event. Has title, time, location, tags, organizers, approval state, etc.
- `RecurringDemonstration`: a series template that generates child demonstrations.
- `Organization`: organizer entity, linked to users via memberships.
- `Organizer`: a person or org inside a demonstration record.
- `MemberShip`: the permissions link between a user and an organization.
- `Case`: admin support cases, logs, and history.
- `User`: login identity, profile, permissions, followers, etc.

Authentication and permissions (who can do what)
-----------------------------------------------

- Flask-Login manages sessions. Users are loaded from MongoDB.
- Permissions are checked by:
  - User roles (global admin, admin, normal user).
  - Organization memberships (`MemberShip`).
  - Decorators in `mielenosoitukset_fi/utils/wrappers.py`.
- Some admin actions log audit entries automatically.

Main parts of the app
---------------------

Public website
- Browsing demos, viewing detail pages, submitting new demos.
- Implemented mostly in `basic_routes.py` with templates in `templates/`.

Admin dashboard
- Demo approval, merge, suggestions, moderation tools, background jobs.
- Implemented under `mielenosoitukset_fi/admin/`.

API
- JSON endpoints for demo listings and some user features.
- Implemented in `mielenosoitukset_fi/api/routes.py`.

Notifications and email
- In-app notifications stored in `notifications` and served via `notifications_bp.py`.
- Email sending uses a queue (`email_queue`) and `EmailSender`.

Background jobs
- APScheduler runs jobs for recurring demos, reminders, previews, and cleanup.
- Job definitions live in `background_jobs/definitions.py`.
- Scheduler and leadership election live in `background_jobs/manager.py`.

Analytics
- Raw view events are stored in `analytics`.
- `run_aggregate.py` rolls them up into `d_analytics`.

How deployment works (in practice)
----------------------------------
To run in production, you need:

- MongoDB
- Redis (Socket.IO and optional cache)
- SMTP server (email)
- S3-compatible storage (uploads)

The Flask app can run in multiple instances. Background jobs use a leadership lock in MongoDB so only one instance actually runs the scheduler.

Config and secrets
------------------
`config.yaml` is the main configuration file. It includes database, mail, S3, and cache settings. For production, make sure you set:

- `SECRET_KEY`
- `MONGO_URI`
- `MAIL_*` settings
- `S3_*` settings

`Config.init_config()` logs warnings if critical settings are missing or still using defaults.

Where to start when debugging
-----------------------------

- Public page broken: start in `basic_routes.py` and the template file.
- Admin feature broken: start in `mielenosoitukset_fi/admin/` for the route, then the template.
- API issue: check `mielenosoitukset_fi/api/routes.py` and `utils/tokens.py`.
- Background job issue: check `background_jobs/definitions.py` and `background_jobs/manager.py`.
- Email issue: check `EmailSender.py` and `email_queue`.

Common commands
---------------

Run locally:

```bash
python3 run.py
```

Run analytics rollup once:

```bash
python3 run_aggregate.py once
```

Send reminders manually:

```bash
python3 run.py demo_sche someone@example.com
```

More docs
---------
- `README.md` has setup and quickstart.
- `docs/admin_dashboard.md` and `docs/admin_users.md` cover admin UI usage.
- `TRANSLATING.md` explains translations.
