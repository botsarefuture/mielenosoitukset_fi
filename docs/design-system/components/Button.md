# Button

`.detail-button` is the public product button: 44px tall, `button-radius`, label in `detail-button`. It has a filled primary variant, an outlined default and a quiet transparent variant. The React detail page uses it, and the calendar's buttons share its geometry.

**Source:** `.detail-button*` in `static/css/public-detail.css`, used in `DemonstrationDetailPage.tsx`, `DetailActions.tsx`, `DetailGallery.tsx` and `FollowButton.tsx`. The in-card variant is `.demo-card-action-btn` in `user-workspace.css`.

## Variants
- **`detail-button--primary`**: the one main forward action in a group (*Tilaa muistutus*, *Osallistun*, *Lähetä*). `product-action-bg` with `product-on-action`, and `product-action-hover` on hover.
- **`detail-button`** (default): secondary actions (*Lisää kalenteriin*, *Ilmoita virheestä*, *Näytä kartta*). `product-surface` with a `product-border` outline and `product-text`. Hover is `product-surface-muted`.
- **`detail-button--quiet`**: low-emphasis and repeated actions (sharing, dialog close, gallery paging). Transparent with an outline.
- **`detail-button--danger`**: cancel and other backing-out actions (*Peruuta*). Always red: `product-danger` text and outline on `product-danger-soft` (5.9:1 in light, 7.3:1 in dark), filling with `product-danger` and `product-surface` text on hover. Maintainer rule, 10 November 2026.
- **`demo-card-action-btn`**: compact actions inside a DemonstrationCard. `product-primary-soft` with `product-primary`.

## What the consumer supplies
A Font Awesome icon (optional, placed first, `aria-hidden`) and a Finnish label. For a toggle, pass `aria-pressed` (Osallistun ↔ Peru osallistuminen). While pending, set `disabled`: the button drops to 0.65 opacity with a `wait` cursor, and the label reads *Lähetetään…* or *Ladataan…*.

## Rules
- One primary per action group. Lay groups out with `detail-actions` (wrapping flex, `action-gap`). Under 560px, buttons stretch to fill the row.
- Inside a detail aside, buttons are full width.
- Never fill a button with `product-primary`. Fills always use `product-action-bg`.
- A cancel action is a button, never a bare text link, and always uses `detail-button--danger`.
- Focus is a 3px `product-primary` outline with a 3px offset. The detail page and its dialogs still use their older `product-accent` ring (see Consistency).
- Use a link (`<a class="detail-button">`) for navigation and a `<button>` for in-page actions.
