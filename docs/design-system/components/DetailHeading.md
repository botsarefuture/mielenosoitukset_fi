# DetailHeading

The top block of a demonstration page: an optional cancelled notice, the title, a definition list of facts (date and time, location), and the primary action row.

**Source:** `EventContent` in `frontend/src/pages/DemonstrationDetailPage.tsx`, styled by `.detail-heading`, `.detail-facts`, `.detail-actions` and `.detail-cancelled` in `static/css/public-detail.css`.

## What the consumer supplies
The event's `title`, `date`, `start_time`, `end_time`, `address`, `city` and `cancelled`, plus action URLs (ICS calendar, reminder, report).

## Rules
- The block is `product-primary-soft` with a `product-border` outline, a 5px `product-primary` top border, `detail-heading-radius` and `detail-heading-padding`.
- The `h1` is `detail-title` in `product-text`, capped at `detail-title-measure` (24ch), and wraps anywhere.
- Facts are a `<dl>`. Each `dt` is `fact-label` in `product-text-muted` with a `product-primary` icon (`fa-calendar-days`, `fa-location-dot`). Each `dd` is `fact-value`, with the time on a second line at weight 500.
- Times use the Finnish dot form here (`17.00–19.00`, `12.00 alkaen`). With no time, show *Kellonaikaa ei ole ilmoitettu*.
- **Actions:** *Tilaa muistutus* (primary), *Lisää kalenteriin (.ics)* and *Ilmoita virheestä*. A cancelled event keeps only the report action.
- **Cancelled:** *Tämä mielenosoitus on peruttu.* is a `role="status"` line in `product-danger` at weight 750, with `fa-ban` and above the title.
