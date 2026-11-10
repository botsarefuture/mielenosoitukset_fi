# Design system

The shared visual and content rules for the public Mielenosoitukset.fi UI. Use it when building or changing any public screen, so new work looks and behaves like the existing pages.

- **This folder** is the versioned copy that agents and developers read: this brand book, `tokens.json` (every token, both themes, with a usage note) and `components/<Name>.md` (one guideline per component).
- **The visual version** with live previews, extracted from `6265edb`, is the Mielenosoitukset.fi Design System artifact on claude.ai (owner's account). Update both together when a rule changes.
- **The code is the source of truth for values.** Token names equal the CSS custom properties in `mielenosoitukset_fi/static/css/product-tokens.css` (`product-surface` is `var(--product-surface)`). If this folder and the CSS disagree, the CSS wins and this folder needs updating.

Components: [SiteHeader](components/SiteHeader.md), [Hero](components/Hero.md), [DemonstrationCard](components/DemonstrationCard.md), [Badge](components/Badge.md), [FilterChip](components/FilterChip.md), [Button](components/Button.md), [FlashMessage](components/FlashMessage.md), [CalendarMonth](components/CalendarMonth.md), [CalendarYear](components/CalendarYear.md), [CalendarScope](components/CalendarScope.md), [DetailHeading](components/DetailHeading.md), [DetailSection](components/DetailSection.md), [SeriesNavigation](components/SeriesNavigation.md), [DetailGallery](components/DetailGallery.md), [ActionDialog](components/ActionDialog.md), [DetailPage](components/DetailPage.md), [ContactOption](components/ContactOption.md).

---

Mielenosoitukset.fi is a Finnish public calendar of demonstrations. The interface is calm, civic and trustworthy: brand blue carries the identity, orange is a rare accent, and the content (the demonstrations themselves) does the talking. Public and admin views share one semantic token foundation, the `product-*` tokens, but each keeps its own layout density.

## Content fundamentals

- **Finnish first.** The public site is Finnish-only today. Write UI copy in Finnish and keep labels short and concrete: *Tulevat mielenosoitukset*, *Kaupungit*, *Ilmoita mielenosoituksesta*, *Kirjaudu sisään*. The `sv` and `en` versions are left to human translators. Never machine-translate them.
- **Plain, neutral, factual.** The site lists demonstrations from every cause, so copy never takes a side. Avoid exclamation marks, hype and emoji.
- **Imperative actions, noun titles.** Buttons name the action (*Hae mielenosoituksia*, *Merkitse luetuiksi*, *Näytä kaikki*). Page titles are nouns (*Kaupungit*).
- **Sentence case** for everything except status badges and language codes, which are uppercase (`TÄNÄÄN`, `PERUTTU`, `FI`).
- **Finnish formats.** Dates are `9.11.2026`, with the weekday written out on the detail page (*maanantai 9.11.2026*). Times are 24-hour in the Finnish dot form, `17.00–19.00`, or `13.00 alkaen` when there is no end time. Cards and details share the same clock helper.
- **Counts agree with their noun:** *1 mielenosoitus*, *3 mielenosoitusta*, *128 osallistujaa*. A duration is written as a duration (*5 päivää 15 tuntia*).
- Feedback is one sentence that says what happened (*Ilmoituksia ei voitu merkitä luetuiksi.*).

## Color

- Page body: `product-text` on `product-surface-muted`. Cards, nav and popovers: `product-surface`. The outermost canvas is `product-canvas`.
- Links, headings, card titles and icon accents use `product-primary`.
- **Filled actions use `product-action-bg` with `product-on-action`** (hover: `product-action-hover`). Never fill a control with `product-primary`: in the dark theme it is a light tint (`#8bb1ff`) that white text cannot sit on.
- Tinted chips, tags and in-card actions use `product-primary-soft` with `product-primary` text.
- `product-accent` (orange) is used sparingly, for highlights, and text on it is `product-on-accent`, never white. Orange used as text is `product-accent-strong`.
- Feedback uses `product-success` on `product-success-soft` and `product-danger` on `product-danger-soft`. Toasts use the `flash-*` set. A status always also carries a word or icon.
- `product-border` is a decorative hairline only (1.3:1 light, 1.8:1 dark). Interactive controls also need a fill or a label to stand out.
- The `pride-*` stops are reserved for Pride events. Badges use `product-pride-gradient` only on the border, with `product-text` on solid `product-surface`; the card keeps its rainbow ring.
- Page styles must not redefine the palette. Admin styles alias these tokens as `--admin-workspace-*`. Public styles never use the admin names.

## Theming

There are two themes, light and dark, built with CSS `light-dark()` and `color-scheme`. The site toggles `html.dark`, and this system uses `data-theme`. A theme changes colors and shadows only, never layout, font sizes, spacing or the order of information.

## Typography

Use **Inter** (Google Fonts, weights 300–800) with the `sans` system stack as fallback. Headings are heavy (800) and tight:
- `hero-title`: hero `h1`, fluid `clamp(2rem, 3.7vw, 3.2rem)`, letter-spacing −0.035em.
- `detail-title`, `calendar-title`, `calendar-month`: left-aligned content-page headings in `product-text`.
- `page-title`: the older centred `h1` in `product-primary`, kept for existing pages.
- `logo`: the wordmark, plain type, 1.5rem/800.
- `section-title`, `card-title`, `detail-body`, `fact-value`, `countdown`, `card-meta`, `body`, `flash-text`: content text.
- `detail-button`, `button`, `fact-label`, `calendar-weekday`, `calendar-count`, `tag`, `badge`, `language`, `header-link`: labels.

## Spacing, shape and elevation

- Card geometry: `card-padding-block` / `card-padding-inline`, with `card-gap` between rows.
- Containers: `header-max-width` (1400px) with `header-padding-inline`. Heroes are `hero-max-width` (1120px) with `hero-padding`.
- Every tappable target is at least `touch-target` (44px).
- Radii are soft. The existing scale runs from `user-radius-small` and `tag-radius` up through `button-radius`, `section-radius`, `card-radius` and `site-hero-radius`, plus `radius-pill`. For new work, use the four canonical steps in *Consistency* below.
- Elevation is soft and diffuse: `product-shadow` for chrome, `card-shadow` → `card-shadow-hover` for cards, `hero-shadow` for heroes. A card lifts 2px and scales to 1.012 on hover.

## Layout patterns

- **Header:** the action-blue gradient bar with the wordmark and the FI/SV/EN switcher, then a white nav bar whose active link has a 3px `product-primary` underline.
- **Hero:** a blue gradient (`hero-start` → `hero-mid` → `hero-end`) with a centred title, one lead line and up to two buttons. **No eyebrow or kicker pill above the title.**
- **Listings:** a toolbar (search, filter chips), then a grid of `DemonstrationCard`s, at least 300px per column.
- **Calendar:** a left-aligned `calendar-title` heading with the submit action on the right, `CalendarScope`, then a `month-calendar-panel` (`CalendarMonth`) or a grid of compact month panels (`CalendarYear`). The grid is always seven columns.
- **Detail page:** `SeriesNavigation` → `DetailHeading` → countdown → a main column (`DetailGallery`, then `DetailSection`s) beside a `detail-aside-width` aside (location, attendance, sharing). Actions open an `ActionDialog`. `DetailPage` is the reference composition.
- **Content pages** (calendar, detail) use left-aligned headings in `product-text`. Centred headings belong only in heroes and on cards.

## States and accessibility

- Every interactive element has a visible `:focus-visible` outline: 3px `product-primary`, or `product-on-action` on blue grounds (see *Consistency*).
- Motion is short (0.18–0.2s ease) and limited to hover lift, color and the toast slide-in.
- The pages ship a skip link (*Siirry sisältöön*) that appears on focus.
- Known source contrast gaps, kept exact and flagged: white on `badge-today` is 3.1:1, the default badge in dark (white on `product-text-muted`) is 1.8:1, and the detail page's `product-accent` focus ring is 2.9:1 on white.

## Iconography

Use **Font Awesome 6** (self-hosted `static/fa/`). `fa-solid` covers actions and places (`fa-city`, `fa-location-dot`, `fa-bullhorn`) and `fa-regular` covers time (`fa-calendar`, `fa-clock`). Icons always sit beside a text label and get `aria-hidden="true"`. Inside cards they are tinted `product-primary`. The verified-organization mark is `mielenosoitukset_fi/static/img/verified.svg` (a single-ink Font Awesome Pro glyph: inline it and fill with `product-primary` when it needs colour). There is no logo file: the brand is the wordmark *Mielenosoitukset.fi* set in `logo`. Don't use emoji.

## Using this system in development

- **Tokens are CSS custom properties with the same names.** `tokens.json` `product-surface` is `var(--product-surface)` in code. In the app the values come from `mielenosoitukset_fi/static/css/product-tokens.css`, which must load before any component stylesheet. Don't copy hex values into components and don't redefine the palette in page CSS.
- **Component classes are the contract.** The classes in each card (`.demo-card*`, `.detail-*`, `.month-calendar*`, `.site-hero`, `.public-filter-chip`, `.flash-*`) are what the React components render. Reuse the component instead of restyling a lookalike. Co-locate new React CSS with the component and consume only `--product-*` tokens.
- **Public UI is React.** New public screens are React components with copy in the TypeScript catalog. Don't add Flask templates or routes for public UI. Admin keeps its `--admin-workspace-*` aliases of the same tokens.
- **Every screen ships** in both themes, at 390px and 1440px, with loading, empty, error and long-Finnish-text states. Every control is at least `touch-target` and has a visible focus ring.

## Consistency: one rule where the pages differ today

The extraction found places where existing screens solve the same problem differently. New and touched work follows the **canonical** rule below. Existing values are kept as tokens so the current pages stay documented.

| Topic | Found in the code | Canonical for new work |
|---|---|---|
| Focus ring | 2px `product-primary` (cards, chips, nav), 3px `product-primary` (calendar), **3px `product-accent`** (detail page and dialogs: 2.9:1 on white, below 3:1) | 3px `product-primary`, offset 3px, on light and dark surfaces; `product-on-action` on blue grounds |
| Buttons | `.detail-button` (8px, 0.94rem/650), `.hero-button` (10px, 750), `.calendar-submit` (0.6rem), `.demo-card-action-btn` (0.5em), header link (10px) | The `Button` contract (`.detail-button`): 44px, `button-radius`, primary / default / quiet, and `--danger` (always red) for cancel. On blue grounds, the hero's white-outline treatment |
| Radii | 6, 7, 8, 9, 10, 12, 14, 16 and 18px, 0.5em, 0.9rem, 1.1em, 1.2em | `tag-radius` 6px for small badges and tags · `button-radius` 8px for controls and cells · `section-radius` 12px for surfaces and dialogs · `site-hero-radius` 18px for heroes · `radius-pill` for status pills |
| Tags | Card tag (0.5em radius, centred, hover fills) vs detail tag (6px, 0.35rem 0.65rem) | One tag: `product-primary` text on `product-primary-soft`, `tag-radius`, weight 600, `#`-prefixed |
| Clock times | Cards and details share `clockLabel`; raw API clocks remain `17:00` | Finnish standard: `17.00–19.00` (dot, en dash, no spaces) and `13.00 alkaen` |
| Page headings | Centred `product-primary` `page-title` (older pages) vs left-aligned `product-text` (calendar, detail) | Left-aligned `product-text`. The front-page hero is the centred exception: title, lead, search and links share one axis |
| Cancelled | `badge-cancelled` `#c0392b` on cards, `product-danger` on the detail page | `product-danger` (`product-danger-soft` for grounds), always with the word *Peruttu* |
| Feedback colours | `flash-*` palette (separate hues) vs `product-success` / `product-danger` | `product-success`, `product-danger` and `product-accent` with their `*-soft` grounds; the `flash-*` set stays only for the existing toast |
| Today | `badge-today` `#ff595e` with white text (3.1:1) on cards, a 2px `product-primary` outline in the calendar | Mark today with `product-primary` (outline or text) plus the word *Tänään* |

## Coverage and gaps

- Taken from `botsarefuture/mielenosoitukset_fi` at `6265edb`. The artifact previews are static HTML renditions of the source markup and CSS, not bundled React components.
- Included: header, hero, listing card, badges, filter chips, buttons, flash, the month and year calendar with its region filter, and the detail page (heading, sections, series, gallery, action dialog, full layout).
- Not included: the legacy `variables.css` palette (retired), Bootstrap 5.3 internals, admin workspace components, the calendar's day agenda list (it reuses `DemonstrationCard`), the submit flow, organization pages and chat, the cities and today screens, and the Leaflet map.
- Font Awesome font files are not copied. Previews load Font Awesome 6.5.2 from cdnjs. Inter is a hosted Google font.
- The hero gradient, badge, Pride and flash colours, and the detail and calendar radii, are hard-coded literals in the source. They are captured here as tokens.
- The language switcher's `color-mix()` tints are approximated with white and black alpha in the previews.
- The gallery preview uses a placeholder image.
