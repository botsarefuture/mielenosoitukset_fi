
### **1. Security & Access Control**

- [ ] **Role Escalation Prevention:** Ensure `compare_user_levels` is consistently used in all critical actions (edit, delete, force password change, create user).
- [ ] **Hard-coded Exceptions:** The `_id == 66c25768dad432ad39ce38d5` exception for Emilia is risky. Consider replacing it with a proper “superuser” flag.
- [ ] **CSRF Protection:** Ensure all POST forms and AJAX endpoints use CSRF tokens.
- [ ] **Input Sanitization:** Currently, username, email, role, and permissions are saved directly. Ensure all inputs are sanitized to prevent injection attacks.
- [ ] **Sensitive Logs:** Avoid printing request.form or other sensitive info to console in production.

---

### **2. Code Quality & Maintainability**

- [ ] **Duplicate Logic:** `edit_user` and `save_user` repeat validation and role checks. Merge or refactor into a helper function.
- [ ] **Deprecated Function:** `is_valid_email` is deprecated—ensure no other code uses it.
- [ ] **Magic Strings & Hard-coded IDs:** Replace `"user"`, `"admin"`, `"global_admin"` with constants/enums.
- [ ] **Permissions Rendering:** The `permission_summary_html` building could be refactored to a Jinja template for cleaner HTML generation.
- [ ] **Logging:** `log_request_info` calls `request.__dict__`, which may expose sensitive info. Consider whitelisting fields to log.

---

### **3. UX / User Experience**

- [ ] **Safe Redirect Loop:** `safe_redirect` uses session counter. Consider adding a `next` fallback parameter to improve UX.
- [ ] **Flash Messages:** Consider using consistent translation keys (`_()` from Flask-Babel) for all messages.
- [ ] **Form Errors:** Highlight invalid fields on forms rather than just flashing messages.
- [ ] **Global Permissions UX:** Consider checkboxes or grouped toggle switches in forms for easier selection.

---

### **4. API & JSON Improvements**

 **JSON vs Form Handling:** Standardize API endpoints to consistently handle JSON and form submissions.
- [ ] **Force Password Change API:** Add `compare_user_levels` check to prevent unauthorized forced resets.
- [ ] **Delete User API:** Currently checks `compare_user_levels` but consider logging deletions with admin ID and timestamp.

---

### **5. Functionality Enhancements**

- [ ] **Pagination:** The user list page loads all users; add server-side pagination for scalability.
- [ ] **Search Improvements:** Support searching by displayname and global permissions.
- [ ] **Audit Logs:** Log every create, edit, delete, and role change with old and new values.
- [ ] **Email Queueing:** Currently sending HTML summaries directly in code; consider templating permissions for better formatting.
- [ ] **Password Reset:** Allow admin to trigger reset email with temporary token link instead of sending raw password.
- [ ] **Bulk Actions:** Implement bulk delete, bulk role change, or bulk permission assignment for admins.
- [ ] **Unit Tests:** Write tests for critical functions: `compare_user_levels`, create/edit/delete user, force password change.

---

### **6. Optional Nice-to-Haves**

- [ ] **Soft Delete:** Instead of hard deletion, mark users as inactive to preserve history.
- [ ] **Two-Factor Authentication:** Optionally enforce MFA for high-level roles.
- [ ] **Super Admin Management:** Separate superuser logic from normal admin roles.
- [ ] **Email Templates:** Move inline HTML permission summary to separate templates.
- [ ] **Activity Feed:** Show recent admin actions in the dashboard for transparency.
