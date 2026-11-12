# CalendarYear

The annual overview: twelve compact month panels in an auto-fit grid. Only days that have events are links. Every other day is a static number, so keyboard users don't have to tab through hundreds of empty days.

**Source:** `frontend/src/app/YearCalendarScreen.tsx` (and `CalendarGrid` with `overview`), styled by `.year-calendar-*` in `calendar.css`.

## What the consumer supplies
The `year`, the optional `city`, and `days[]` for the whole year.

## Rules
- Months use `minmax(min(100%, 24rem), 1fr)` columns with a 1.25rem gap. Panels are padded 0.75rem.
- Each month heading links to that month's full view, with a 44px hit area. Under it sits a muted total (*4 mielenosoitusta*).
- Cells are 44px tall and set at 0.9rem. Cells with no events are `calendar-static-day`: `product-text-muted` on `product-surface`. Today keeps its 2px `product-primary` border.
- Year navigation reads *← 2025 · Tämä vuosi · 2027 →*.
