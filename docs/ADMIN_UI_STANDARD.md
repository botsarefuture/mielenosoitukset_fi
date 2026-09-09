# Admin UI standard

This document is the contract for every view rendered inside the administration
application. New admin pages should look like part of the same product without
adding page-specific colors, controls, tables, or theme logic.

## Foundations

- Every full admin template extends `admin_base.html` and renders its page in
  `main_content`. Partials and email templates are the only exceptions.
- `admin_base.html` owns theme initialization, the sidebar, the content width,
  flash messages, and the footer.
- `static/css/admin/workspace.css` is loaded after page styles and owns shared
  components. Do not recreate these components in a template `<style>` block.
- Both themes use the same geometry and hierarchy. A theme may change colors
  and shadows, but not layout, font sizes, spacing, or information order.

## Canonical tokens

Use only the `--admin-workspace-*` semantic tokens for new shared UI:

- `--admin-workspace-surface` and `--admin-workspace-surface-muted`
- `--admin-workspace-text` and `--admin-workspace-muted`
- `--admin-workspace-border` and `--admin-workspace-shadow`
- `--admin-workspace-blue`, `--admin-workspace-blue-dark`, and
  `--admin-workspace-blue-soft`
- `--admin-workspace-primary-bg`, `--admin-workspace-primary-hover`, and
  `--admin-workspace-on-primary` for filled primary actions; accent blue is not
  a safe filled-button background in every theme
- `--admin-workspace-orange` and `--admin-workspace-orange-soft`

Legacy token names are temporarily aliased in `workspace.css`. They are a
migration aid, not an API for new code. Never hardcode a light-only surface or
text color. Semantic success, warning, and danger colors must keep readable
contrast in both themes.

## Page structure

Use these shared classes:

- `.admin-content`: base-owned page width and text context.
- `.admin-workspace` or `.admin-page`: page shell.
- `.admin-page-hero`: primary page introduction. Add
  `.admin-page-hero--stacked` when actions belong below the copy.
- `.admin-page-hero__kicker`, `__actions`, `__action`, and `__metric`: hero
  elements.
- `.admin-workspace-summary` and `-card`: at-a-glance metrics.
- `.admin-workspace-toolbar` or `.admin-list-toolbar`: search, filters, and bulk
  actions.
- `.admin-workspace-table`: responsive table surface.
- `.admin-confirm`: destructive or consequential confirmation page.

Use a compact heading instead of a hero only for detail editors and short
workflows. The first screenful must still have one clear title, a short purpose
statement, and consistently placed primary actions.

## Lists and tables

All collection views share the same interaction model regardless of whether
their content is a table, list group, or cards:

1. Page introduction.
2. Optional summary metrics.
3. Search/filter toolbar.
4. Bulk-action and selection status.
5. Collection surface.
6. Empty state and pagination.

Tables use `.admin-workspace-table` around a semantic `<table>`. On small
screens the wrapper scrolls horizontally; cells must not be converted into
anonymous block elements.

Multi-selection always uses square checkboxes in the first column. A selected
row receives both a tinted surface and a leading accent. Select-all must ignore
disabled and filtered-out rows, expose its indeterminate state, and update an
`aria-live` count. Radios are reserved for choosing exactly one mutually
exclusive option.

## Forms, actions, and states

- Use Bootstrap form markup; the shared layer supplies theme-aware controls,
  labels, help text, focus rings, and disabled states.
- Compose larger forms with `.admin-form-page`, `.admin-form-layout`,
  `.admin-form-section`, `.admin-form-grid`, `.admin-field`, and
  `.admin-sticky-actions`; reusable repeaters, previews, and guidance use the
  corresponding shared `admin-*` primitives rather than template-local CSS.
- Use `.btn` variants rather than inventing page-specific buttons.
- Primary is for the main forward action, secondary/outline for navigation,
  and danger only for destructive actions.
- Status badges are concise and never the sole carrier of meaning.
- Every interactive element needs a visible `:focus-visible` state.
- Browser `alert()`, `prompt()`, and `confirm()` should be migrated to the
  shared modal/toast pattern when the surrounding workflow is next edited.

## Modals

Bootstrap owns `.modal`. Never define layout or visibility on the global
`.modal` selector. The old edit-link dialog is isolated as
`.legacy-admin-modal` until it can be converted to Bootstrap. Modal content
inherits the active admin theme.

## Review checklist

- Uses `admin_base.html` and `main_content`.
- No standalone document, duplicate font/icon imports, or page-owned theme
  switch.
- No `bg-white`, `text-dark`, or hardcoded neutral surface in admin markup.
- Shared cards, controls, lists, tables, confirmations, and modals are reused.
- Light and dark modes preserve readable text and identical layout.
- Keyboard focus, labels, empty states, bulk selection, and mobile overflow are
  understandable without guessing.
