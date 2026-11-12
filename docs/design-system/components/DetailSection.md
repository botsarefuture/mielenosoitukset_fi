# DetailSection

The white card that holds each block of the detail page (Kuvaus, Reitti, Järjestäjät, Sijainti, Osallistun, Jaa tapahtuma), along with the countdown strip and the tag row.

**Source:** `.detail-section`, `.detail-countdown`, `.detail-prose`, `.detail-route`, `.detail-organizers`, `.detail-tags`, `.detail-attendees` and `.detail-location` in `static/css/public-detail.css`.

## What the consumer supplies
An `h2` (`section-title`) and the content: sanitised description HTML, route stops, organizers (`name`, `organization_id`, `website`, `email`, `logo`), tags, or the location with OpenStreetMap coordinates.

## Rules
- A section is `product-surface` with a `product-border` outline, `section-radius` and `section-padding`, and sits 1.75rem from the next one. Never nest sections.
- Prose is `detail-body`. A quote has a 3px `product-accent` left rule with muted text.
- Organizers are a plain list separated by `product-border` hairlines. Logos are 48px with `choice-radius`. A hidden name reads *Yksityishenkilö (nimi piilotettu)*. External links end with `fa-arrow-up-right-from-square` and open in a new tab with `rel="noopener noreferrer"`.
- Detail tags are `#tag` links on `product-primary-soft` with `tag-radius`. These differ from the card tags: see README › Consistency.
- **Countdown:** a muted label (*Aikaa mielenosoituksen alkuun*) above a `countdown` value with tabular numerals. Hide it once the event starts or if it is cancelled.
- The map loads only on demand (*Näytä kartta*), at `map-height`.
- Buttons in the aside are full width.
