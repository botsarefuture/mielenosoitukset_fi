# ActionDialog

The modal for detail-page actions: subscribing to a reminder, reporting an error (a two-way choice, then a form), and inviting friends. It is built on the native `<dialog>`.

**Source:** `Dialog`, `ReportChoice`, `ReportForm`, `ReminderForm` and `InviteForm` in `frontend/src/components/detail/DetailActions.tsx`, styled by `.detail-action-dialog`, `.detail-choice*`, `.detail-form`, `.detail-checkbox` and `.detail-feedback` in `public-detail.css`. The preview shows the dialog inline, without its backdrop.

## What the consumer supplies
A title, a close label (*Sulje*) and the form. A form's feedback message comes from the API response.

## Rules
- The dialog is at most 560px wide (92vw), `product-surface`, with `section-radius` and 1.5rem padding. The backdrop is `product-overlay`.
- The header is the `h2` title with a quiet close button.
- **Report choice:** two equal cards with `choice-radius`. The recommended path (*Korjaa tiedot muokkauslomakkeella*) has a `product-accent` border and a primary button.
- **Forms:** labels at weight 600, inputs 44px tall with `input-radius`, checkboxes 18px in `product-primary` with a 44px row. The submit button is primary and disabled while pending (*Lähetetään…*).
- **Feedback:** `detail-feedback`, `is-success` in `product-success` (`role="status"`) or `is-error` in `product-danger` (`role="alert"`). A successful form hides itself.
- The focus ring inside the dialog is currently 3px `product-accent`: see README › Consistency.
