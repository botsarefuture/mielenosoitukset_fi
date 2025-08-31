### **TODOs for `admin_org` module**

**1. General / Infrastructure**

- [ ] Add **unit tests** for all routes and helper functions (#174).
- [ ] Implement **pagination** for the organization control panel (#175).
- [ ] Add **error handling** for all database operations (#176).
- [ ] Refactor common repeated code (e.g., fetching organization, validating forms) into **utility functions** (#177).
- [ ] Improve the **user interface** for organization forms (#178/#179).

**2. Organization Management**

- [ ] Confirm `insert_organization` handles all optional fields correctly.
- [ ] Make sure `update_organization` properly validates fields before updating.
- [ ] Ensure **social media links** are stored consistently.

**3. Invitations**

- [ ] Ensure `invite_to_organization` handles duplicate invitations correctly.
- [ ] Add **unit tests** for:

  * `force_accept_invite` API
  * `cancel_invite` API
  * `set_invite_role` API
- [ ] Implement **automatic user creation** if `force_accept_invite` is called with a non-existing user (#387).

**4. Membership / Roles**

- [ ] Improve `change_access_level` to properly check for permissions before updating roles.
- [ ] Consider **logging** all role changes for audit purposes.
- [ ] Add checks for **superuser or org-level admin** when deleting memberships (#342).

**5. Misc / Enhancements**

- [ ] Convert all flash messages to use **consistent language** (some are in Finnish, some in English).
- [ ] Review all deprecated imports or duplicate imports (e.g., `ObjectId` imported twice).
- [ ] Add **input validation** for API endpoints (emails, ObjectId formats, roles).
- [ ] Implement **confirmation step** for destructive API actions (delete membership, cancel invite).