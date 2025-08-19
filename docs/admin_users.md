Admin — User Management

Overview
--------
This page documents the admin user management interface and the improvements made to match the rest of the admin UIs.

Key changes
-----------
- Consolidated per-user actions into a single dropdown to reduce visual clutter.
- Added links inside each user action dropdown to:
  - Edit the user
  - View the user
  - View the user's edit history
  - Delete the user (if you have the permission)
- Delete confirmation uses a shared `deleteModal.js` behavior with fast-delete (hold Shift to delete instantly).
- The edit page contains improved help text, clearer confirmed checkbox, and Cancel button.

Keyboard and shortcuts
----------------------
- Shift: toggle fast-delete mode (hold Shift then click Delete to bypass the confirmation modal).
- Escape: close an open modal.

Developer notes
---------------
- The user list template is `templates/admin_V2/user/list.html`.
- The edit page is `templates/admin_V2/user/edit.html`.
- Deletion uses the shared `static/js/deleteModal.js` which expects the confirm button to have id `confirmDelete` and sets `data-type` to `user`.

