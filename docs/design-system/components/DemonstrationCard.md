# DemonstrationCard

The listing card for one demonstration: status badges, an optional 16:9 cover, a centred title and date, time and location rows, tags, and a friends-attending row. The whole card is a link.

**Source:** `frontend/src/components/listings/DemonstrationCard.tsx`, styled by `.demo-card*` in `static/css/user-workspace.css`.

## What the consumer supplies
- A `Demonstration`: `title`, `date` / `formatted_date`, `start_time`, `end_time`, `city`, `address`, `tags[]`, `cancelled`, and an optional `cover_picture`.
- `detailUrl`, `seriesUrl` and `tagUrl` templates (`__ID__`, `__TAG__`).
- Optionally, friends attending (`authenticated` plus the attendance endpoint).

## Rules
- Lay cards out in a grid that is at least 300px wide per column, with the card itself taking `role="link"` and `tabindex="0"`. Enter or a click opens the detail page. Clicks on inner links and buttons stay on those links.
- The title is set in `card-title`, in `product-primary`. Meta rows are `card-meta` in `product-text-muted` with `product-primary` Font Awesome icons (`fa-calendar`, `fa-clock`, `fa-city`, `fa-location-dot`).
- Time reads `17.00–19.00`. With no end time it reads `13.00 alkaen`. Cards and details reuse `clockLabel` from `frontend/src/components/detail/content.ts`; API clocks retain their colon format.
- At rest the card has a 1.5px `product-primary-soft` border and `card-shadow`. Hover and focus switch to a `product-primary` border and `card-shadow-hover`.
- A `pride` tag adds `.demo-card-pride` (the six-stop `pride-*` ring) and a Pride badge.
- Titles and addresses wrap anywhere. Never truncate them.
