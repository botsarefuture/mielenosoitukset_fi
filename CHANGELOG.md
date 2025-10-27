# Changelog

**Note:** This changelog is **not fully up-to-date**. Some recent features, fixes, or changes may not be reflected here.

---

Got it! Here's the updated entry with the correct version:

---

## v4.0.0-beta.1 – *Robots Control Edition* 🌟

### Added

* `/robots.txt` route implemented to control web crawlers.
* Disallows access to sensitive paths:
  `/admin/`, `/users/auth/login/`, `/users/auth/register/`, `/users/auth/forgot/`.

### Purpose

* Prevents automated bots from indexing or interacting with admin and authentication routes.
* Ensures normal users can access the site without restrictions.

### Notes

* Returns proper `text/plain` content for compatibility with all crawlers.


## v4.0.0-beta – *Campaign & Admin Revolution Edition* 🌟

### Security & Access
- Adds safe redirect and temporary superuser access for Emilia to prevent system hijacking.
- Plans v4.1.0: Introduce proper access levels; Emilia will be assigned highest access via the system.

### Features
- Admin UI major update for improved usability and layout.
- API support for cancelling and force-accepting organization invitations.
- Demonstration enhancements: recommendations, badges, edit history, and diff views.
- Campaign volunteer signup API with email confirmation and expiry.
- Caching added to improve performance.

### Fixes
- Resolves DOM re-interpretation and duplicate data issues.
- Fixes login redirect flow and forced password reset.
- Redis issues resolved.
- Minor UI and form fixes.

### Dependency Updates
- `pymongo` upgraded 4.6.1 → 4.6.3
- `apscheduler` upgraded 3.10.4 → 3.11.0


## v3.1.0 – *The Reminder Revolution Edition* 🌟

### New Features

* **Email Reminder System**: Implemented a robust system for demonstration reminders, including `.ics` calendar attachments compatible with Gmail and Google Calendar.
* **Popup/Modal UI for Reminders**: Introduced a fully accessible and responsive modal interface for subscribing to reminders, supporting both light and dark modes.

### Fixes

* **Critical Crash Resolutions**: Fixed crashes occurring during profile picture uploads; improved data synchronization reliability.
* **.ics Attachment and Encoding**: Resolved issues with `.ics` encoding to ensure full calendar compatibility.

### Updates

* **Performance Optimization**: Migrated legacy features and optimized module interactions.
* **Deprecation Guidelines**: Revised to align with updated project standards.
* **Email Sending Refactor**: Improved email sending infrastructure with robust `.ics` attachment handling and error management.

---

## v3.0.0 – *Evolution Edition* 🚀

### New Features

* **Redesigned UI**: Introduced a responsive layout with refined grid system and updated color themes.
* **Enhanced Field Naming**: Standardized all field names using underscore formatting.

### Fixes

* **Critical Crash Resolutions**: Addressed issues causing application crashes during profile picture uploads.

### Updates

* **Performance Optimization**: Optimized legacy modules and internal interactions.
* **Deprecation Guidelines**: Updated to reflect current project standards.

---

## v2.9.2 – *Bug Squashing Edition* 🌟

### Fixes

* **Critical Bug Fix**: Resolved a crash issue during profile picture uploads.
* **Minor Bug Fixes**: Various small bug fixes improving overall app stability.

---

## v2.8.6 – *Organization Enhancement Edition* 🌟

### New Features

* **API Endpoint for Organizations**: Added support for creating new organizations via API.

### Updates

* **Organization Insertion Logic**: Improved data integrity checks for organization creation.
* **Admin Interface**: Enhanced UI for organization management.

---

## v2.8.5 – *Organizer Fix Edition* 🌟

### Fixes

* **Organization ID Assignment**: Corrected handling of `None` values in `fix_organizers` function.

---

## v2.8.4 – *Modernization Edition* 🌟

### Updates

* **Flask Upgrade**: Updated to latest Flask version for improved security and performance.
* **Dependency Management**: Upgraded all dependencies to their latest versions.
* **Documentation Overhaul**: Removed outdated docs and added comprehensive guides.
* **Codebase Cleanup**: Refactored and removed deprecated methods to improve maintainability.

---

## v2.8.3 – *Structural Overhaul Edition* 🌟

### Updates

* **Project Structure**: Refactored codebase structure, removed unused files, and added new modules.
* **Email Templates**: Improved templates for higher user engagement.
* **JavaScript Enhancements**: Improved JS functionality for a smoother user experience.

---

## v2.8.2 – *Polished Performance Edition* 🌟

### Deprecations

* **Leaflet Attribution Control**: Deprecated method for hiding Leaflet attribution control.

### Updates

* **Logging**: Adjusted logging level for recurring demonstrations.
* **Type Checking**: Enhanced type validation in the Demonstration class.
* **Documentation**: Improved script documentation and copyright notices.

---

## v2.8.1 – *Sparkly Bug Fix Edition* 🌟

### Fixes

* **Critical Bug Fix**: Resolved profile picture upload crash issue.
* **Minor Bug Fixes**: Multiple minor bug fixes to improve stability.

### Updates

* **Dependency Upgrades**: Updated packages for better performance and security.

### Deprecations

* **Feature Removals**: Removed outdated or unused functionality.

---

## v2.8.0 – *Ultimate Glow-Up Edition* 🌟

### New Features

* Enhanced user profiles with custom avatars, themes, and animations.
* Advanced role management with personalized permissions.
* Smart notifications with emojis, sound effects, and customizable settings.
* AI-driven personalization for user experience.
* One-click settings synchronization across devices.
* Improved privacy and security measures.
* Guardian Mode for automated threat detection.

### Fixes

* Optimized data synchronization.
* Improved startup stability and crash resistance.

### Updates

* Dependency and performance optimization for faster and more efficient operations.

---

## v2.7.0 – *Navigator’s Dream Edition* 🌟

### New Features

* **Language Navigation 2.0**: Introduced advanced translation and localization support.

---

## v2.6.0 – *Foundation for Greatness Edition* 🌟

### New Features

* Advanced authentication, including face recognition.
* Fortress-level encryption for sensitive data.
* UI enhancements and cleaner design updates.
* Expanded language support and emoji integration.

### Fixes

* Optimized data syncing and improved crash resistance under high load.

### Updates

* Backend component upgrades for scalability and performance.
* Refined codebase for better efficiency.

---

## [Unreleased]

### Added

* Automatic email notifications to `tuki@mielenosoitukset.fi` when a new demonstration is submitted.
* Reminder subscription system for demonstrations via email (1 week prior, day before at 9:00, day of at 9:00 or at least 2 hours before).
* Reminder subscription popup/modal UI with light/dark mode support.
* Popups and modals now appear above the header (`z-index: 1000001` for backdrop, `1000002` for modal).
* Main CSS and button styles now use color variables and `light-dark()` for full theme support.

### Changed

* UI containers and popups improved for contrast, spacing, and clarity.
* Reminder subscribe button grouped with social/share buttons.

### Fixed

* Modals and popups never hidden behind the header.
* Removed unnecessary borders from stacked containers for cleaner UI.

---

✅ **Overall:** Improved security, performance, accessibility, and polished UI for a more professional and reliable experience.