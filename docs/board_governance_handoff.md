# Board Governance Handoff

Status: in progress on branch `fix-board-compliance-approval`

## Shipped In This Branch

- Added board-request based governance for `god` and `global_admin`.
- Added `board_member` role-based access to the board clearance and board audit surfaces.
- Blocked manual promotion to `god` / `global_admin` from the normal admin user editor.
- Required board-request flow for demoting `god`.
- Added tamper-evident integrity signatures for board requests so raw DB edits do not silently grant or preserve privileged access.
- Updated the board UI and audit UI to reflect request status more clearly.
- Added focused regression coverage in `tests/test_board_compliance.py`.

## Important Security Model

- `god` and `global_admin` are board-managed roles.
- Requests require:
  - approval document URL
  - approval document SHA256
  - approval from all active `board_member` users
- Approved requests automatically apply the target role.
- Direct DB edits to request payloads invalidate the request integrity signature.
- Invalid requests no longer count as active clearance and cannot receive more votes.

## Remaining Work

1. Add stronger board-audit detail views.
   - Show full request lifecycle grouped by request ID instead of only flat events.
   - Include integrity-failure markers directly in the audit listing.

2. Add upload-based approval-document handling.
   - Replace URL-only input with actual managed file upload if that is the intended long-term path.
   - Store immutable metadata for the uploaded approval document.

3. Harden board-member lifecycle.
   - Decide whether `board_member` itself should become board-managed.
   - Add protections for removing the last active board member.

4. Add dedicated admin tests for self-edit and privileged role transitions.
   - Explicit `god` self-edit success path.
   - Explicit rejection for manual `global_admin` promotion.

5. Rework `/board/audit/ui` further.
   - Improve filtering and request grouping.
   - Replace remaining internal action vocabulary with user-facing language everywhere.

6. Consider moving board-request signing off the main app secret.
   - `BOARD_APPROVAL_SIGNING_KEY` exists now and falls back to `SECRET_KEY`.
   - Production should set it explicitly.

## Validation Already Run

- `python -m pytest -q tests/test_board_compliance.py --maxfail=1`
- `python -m py_compile config.py mielenosoitukset_fi/admin/board_compliance.py tests/test_board_compliance.py`

## Caution

- `.codex` is untracked local noise and should stay out of commits.
- This branch contains a broad board-governance slice; do not mix unrelated preview/admin tasks into it.
