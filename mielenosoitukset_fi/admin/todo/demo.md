### **1. Functionality**

- [ ] Make sure all CRUD operations are fully tested: create, edit, duplicate, delete.
- [ ] Implement full `edit_demo_with_token` workflow (POST handling + validation is done, but verify edge cases).
- [ ] Verify `approve_demo_with_token`, `reject_demo_with_token`, and `preview_demo_with_token` handle expired/invalid tokens correctly.
- [ ] Test `send_edit_link` and `generate_edit_link` for multiple submitters.
- [ ] Make `recommend_demo` properly check superuser status and handles edge cases (like missing date).
- [ ] Filter logic in `demo_control()`:

  - [ ] `$or` queries for non-global admins might override `show_hidden`; double-check correctness.
  - [ ] Search filtering only applies to `"title"`, `"city"`, `"address"`; maybe include tags/topics.
- [ ] `filter_demonstrations()`:

  - [ ] Consider returning `past_demos_count` to the template (currently calculated but unused).
  - [ ] Ensure that `route` filtering works if needed in the future.

---

### **2. Security / Permissions**

- [ ] Make sure `SECRET_KEY` is set from environment/config, not hardcoded.
- [ ] All `*_with_token` routes should enforce a short expiry and one-time use if needed.
- [ ] Validate user permissions carefully when showing hidden demos or filtering by orgs.
- [ ] Ensure email templates do not leak sensitive info (like internal IDs) to submitters.
- [ ] Escape all user-input data in HTML diffs (`html_diff` is okay, but check templates).

---

### **3. UX / Admin Interface**

- [ ] Add pagination or lazy loading to `demo_control()` dashboard if many demos exist.
- [ ] Show flash messages consistently after actions (approve/reject/create/edit/delete).
- [ ] Include preview links on dashboard for quick access.
- [ ] Improve diff view styling for readability (currently basic `<span>` tags).
- [ ] Consider including a “copy link” button for edit and preview links.

---

### **4. Cleanup / Optimization**

- [ ] Remove duplicate imports (e.g., `flash_message` is imported twice).
- [ ] `ObjectId` imported multiple times; consolidate.
- [ ] Consider moving helper functions (`is_valid_latitude`, `collect_organizers`) to a utils file if reused elsewhere.
- [ ] Logging: use `logger` consistently instead of `print`.
- [ ] Maybe extract S3 upload logic to a service class for clarity.

---

### **5. Future Enhancements**

- [ ] Add support for tagging organizers or demos for better filtering.
- [ ] Implement a history diff download (PDF/CSV) for audit purposes.
- [ ] Automatically notify org admins when a demo is approved/rejected.
- [ ] Add admin dashboard stats: total demos, approved, pending, past, future.
- [ ] Support multiple languages in flash messages and emails (currently `_()` used in some places).
