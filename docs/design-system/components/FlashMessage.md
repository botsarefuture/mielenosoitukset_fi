# FlashMessage

A toast notice for the result of an action, in four categories (success, error, warning, info), with an icon disc, a message and a close button.

**Source:** `static/css/flash.css`, rendered in `templates/base.html` (`#flash-messages`). This is a static rendition: the slide-in and the 5-second progress bar are not shown.

## What the consumer supplies
The category (`flash-success`, `flash-error`, `flash-warning`, `flash-info`) and one short Finnish sentence.

## Rules
- Each category tints `flash-card-bg` with its `flash-*-bg`, outlines it in `flash-*-border` and uses `flash-*-icon` for the 4px left rule, the icon and the progress bar. The text is `flash-*-text`.
- Errors use `role="alert"`. The other categories use `role="status"`.
- Every category carries its own icon (`fa-circle-check`, `fa-circle-exclamation`, `fa-triangle-exclamation`, `fa-circle-info`), so colour is never the only signal.
- Stack toasts at the top right, at most `flash-max-width` wide, with a 1rem gap. Inline notices add `.flash-message--inline`.
