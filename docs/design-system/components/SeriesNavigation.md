# SeriesNavigation

A horizontally scrolling strip of a recurring event's occurrences. The current one is highlighted, and cancelled ones are dimmed.

**Source:** `SeriesNavigation` in `DemonstrationDetailPage.tsx`, styled by `.detail-series*` in `public-detail.css`.

## What the consumer supplies
`series.title` and `series.occurrences[]`, each `{id, url, date, start_time, cancelled}`, plus the current `id`.

## Rules
- It is a `<nav>` labelled with the series title. Each item is a link showing the date in weight 650 and, under it, the start time or *Peruttu* in muted small text.
- The current item gets `aria-current="page"`, a `product-primary` border and a `product-primary-soft` fill. A cancelled item is at 0.7 opacity and always says *Peruttu*.
- Items use `button-radius` and never wrap. The row scrolls sideways instead.
