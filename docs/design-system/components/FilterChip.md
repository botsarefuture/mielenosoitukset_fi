# FilterChip

An active search filter shown above a listing, with a 44px remove button.

**Source:** `.public-filter-chip` in `static/css/user-workspace.css`, rendered by `frontend/src/components/listings/ListingTools.tsx`.

## What the consumer supplies
The filter's label (a city, a tag, a date range) and an `aria-label` for the remove button that names the filter.

## Rules
- A `product-surface-muted` fill, a `product-border` outline and `user-radius-small`.
- The remove button is at least `touch-target` on both axes, with a 2px `product-primary` focus outline.
- Long labels wrap. Never truncate them.
