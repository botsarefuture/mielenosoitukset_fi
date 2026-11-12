# CalendarMonth

The month calendar page. It has a heading with the submit action, a region filter, and a panel with month navigation, a summary line, a seven-column grid of day links with event counts, and a footer line.

**Source:** `frontend/src/app/CalendarScreen.tsx` and `CalendarGrid.tsx`, styled by `frontend/src/app/calendar.css`.

## What the consumer supplies
- `period` (`year`, `month`, optional `city`) and `days[]` as `{date, count}` from the calendar API.
- The selected `day`, if any. It gets `aria-current="date"` and links to `?day=N#calendar-agenda`.
- Today's date, in Helsinki time.

## Rules
- The grid is a real `<table>` with a hidden `<caption>` (`calendar-sr-only`) and `th scope="col"` weekdays *Ma Ti Ke To Pe La Su*. The week starts on Monday. The grid stays seven columns at every width and never stacks.
- **Day cell:** at least `calendar-cell-height`, `button-radius`, `product-canvas` fill and a `product-border` outline. On hover the border turns `product-primary` and the fill `product-primary-soft`.
- **Today:** a 2px `product-primary` border and an underlined number.
- **Selected:** `product-action-bg` with `product-on-action`.
- **Count:** a `calendar-count` pill in `product-primary-strong` on `product-primary-soft`. The full sentence lives in the link's `aria-label` (*9.11.2026, 3 mielenosoitusta, tänään*), so the pill is `aria-hidden`.
- Navigation and secondary buttons are 44px with `product-primary-strong` text on `product-canvas`. *← Edellinen* and *Seuraava →* carry an `aria-label` that names the month.
- The focus ring is 3px `product-primary`, offset 3px.
- The month name is lower-case Finnish (*marraskuu 2026*). CSS capitalises it.
- Errors use `calendar-notice` with *Kalenterin lataaminen epäonnistui.* and a *Yritä uudelleen* button.
