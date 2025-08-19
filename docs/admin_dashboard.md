Admin Dashboard — Quick Usage Guide

Overview
--------
This page explains the admin `Demonstrations` dashboard and how to use the actions available for each demonstration in a clear and user-friendly way.

Goals
-----
- Reduce visual clutter by consolidating per-row actions into a single dropdown.
- Make important functions discoverable: view, edit, accept, recommend, view edit history, view submitter info, and delete.
- Provide keyboard shortcuts for power users.

Per-row actions (dropdown)
--------------------------
- Hyväksy (Accept): Visible when the demo is not approved and you have `ACCEPT_DEMO` permission.
- Suosittele (Recommend): Visible for global admins. Confirms before sending recommendation.
- Muokkaa (Edit): Opens the edit form for the demo (if you have `EDIT_DEMO`).
- Katsele (View): Opens the public detail view.
- Ilmoittaja (Submitter): Opens a modal with the submitter's name, email, role, whether they accepted terms, and submission timestamp.
- Muokkaushistoria (Edit history): Opens the edit history page which lists previous edits and allows viewing diffs.
- Poista (Delete): Opens a confirmation modal; hold Shift while clicking Delete (anywhere) to perform a fast delete without the confirmation modal.

Keyboard & accessibility
------------------------
- Shift (hold): toggles fast-delete mode. When active, Delete entries trigger immediate deletion without showing the modal.
- Escape: closes open modals.

Notes for admins and developers
-------------------------------
- All actions respect the current user's permissions. If an item is disabled in the dropdown, you lack the necessary permission.
- Edit history is available from the dropdown for every row — this links to the existing `/admin/demo/edit_history/<demo_id>` route.

Troubleshooting
---------------
- If submitter info is empty, check server logs to ensure `/admin/demo/get_submitter_info/<demo_id>` returns a JSON object like:
  {
    "status": "OK",
    "submitter": {
      "submitter_name": "Pihka",
      "submitter_email": "pihka.pirinen@protonmail.com",
      "submitter_role": "järjestäjä",
      "accept_terms": true,
      "submitted_at": "2025-08-13 17:19:27.688000"
    }
  }

Feedback & future improvements
------------------------------
- Add inline tooltips to each dropdown item to briefly explain their effects.
- Add undo for delete (soft-delete + trash view) to reduce accidental removals.

