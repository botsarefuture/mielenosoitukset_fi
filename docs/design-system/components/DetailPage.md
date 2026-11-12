# DetailPage

The whole demonstration page composed from its parts: series strip → DetailHeading → countdown → a two-column layout (gallery, description, route, organizers and tags on the left; location, attendance and sharing in the aside). Loading and not-found states follow. Use this card as the reference layout for any new public detail screen.

**Source:** `frontend/src/pages/DemonstrationDetailPage.tsx`, hosted by `DetailScreen.tsx`, styled by `static/css/public-detail.css`.

## What the consumer supplies
`DetailProps`: the endpoint, `id`, `locale`, `messages`, `urls`, `authenticated`, series data and the follow state. The page fetches the event itself (`useDemonstration`).

## Rules
- The page is `calc(100% - 3rem)` wide (2rem under 560px), with 2rem above and 4rem below.
- `detail-layout` is `minmax(0, 1fr)` plus `minmax(260px, detail-aside-width)` with `detail-layout-gap`. Under 850px the aside drops below and splits into two columns, and under 560px into one.
- **Loading:** a `product-primary` 5px bar beside *Ladataan tapahtuman tietoja...* (`role="status"`, `aria-busy`).
- **Not found:** a `section-radius` card reading *Tapahtumaa ei löydy tai se ei ole julkinen.* with a link back to *Kaikki mielenosoitukset*. An error adds a primary *Yritä uudelleen*.
- The page sets `document.title` to `<title> | Mielenosoitukset.fi` and tracks one view per event.

**Known source gap:** `.detail-heading` has no bottom margin, so the countdown card sits flush against it. New work should leave `detail-layout-gap` between them.
