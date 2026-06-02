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
- User deletion is a top-level destructive action: the actor must have both `DELETE_USER` and top-level approval (`global_admin`/`god`).
- Deleting a user removes direct personal-data links, including submitter and support records, but does not automatically delete demonstrations they submitted through the public submission flow.
- Submitted demonstrations are shown in the delete impact estimate for separate support/admin review if event removal is also needed.
- The delete confirmation modal fetches and displays an impact estimate before the final confirmation, including how many submitted demonstrations need separate review and how many directly related records will be removed.
- Users can request account deletion from their own settings page. The request is stored in `account_deletion_requests` and emailed to `tuki@mielenosoitukset.fi`; support/admins still perform the approved deletion.
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
- User deletion cleanup is implemented in `admin/admin_user_bp.py` via `_delete_user_personal_data`; keep that helper in sync with any new collection that stores user personal data.
- User deletion clearance is enforced server-side in `admin/admin_user_bp.py`; do not rely on template-only hiding for this action.
