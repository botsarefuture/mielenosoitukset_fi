# FundraisingBar

A slim, sticky notice above the public header that points to the fundraising page. Off by default.

**Source:** `frontend/src/components/fundraising/FundraisingBar.tsx`, phase and dismissal logic in `frontend/src/app/fundraising-bar.ts`, styled by `static/css/fundraising-bar.css`. Copy is `fundraisingBar` in `frontend/src/app/i18n.ts`.

## Look
- Surface `product-accent-soft` with a 3px `product-accent` top edge and a `product-border` hairline below; text in `product-text`, 15px at weight 600 (14px under 720px).
- 56px tall on desktop and 48px on mobile, fixed through `--fb-h`, so nothing shifts. Content is centred in the header's 1400px, 2rem grid.
- One filled primary button (`product-action-bg`, 40px, 8px radius, 650 weight; in dark mode a 1px light inner edge so it reads against the warm surface) and one ghost secondary (`product-primary` text, soft tint on hover). The close control is a plain 40px icon button with a soft hover circle at the right edge. Focus is the 3px `product-primary` outline with a 2px offset.
- No icon in the message and no pill. Copy is Finnish, in sentence case, without exclamation marks.

## Behaviour
- Before the start date: "Pienkeräys aukeaa 16.11." and a primary "Lue lisää". From the start date to the end date, inclusive, and only when the collection is confirmed and active: "Pienkeräys on käynnissä 15.2. asti" (mobile "Keräys on käynnissä"), a ghost "Lue lisää" and a primary "Lahjoita" that links to the donation block. Otherwise and after the end date the bar is absent.
- Dates come from the fundraising configuration (`show_bar`, `start_date`, `end_date`, or the planned dates before confirmation); the phase is decided on the Helsinki date. A tab left open moves to the next phase within a minute.
- Hidden on `/keräys`. When the bar flag is on the header's "Tutustu pienkeräykseen" link is not shown.
- Dismissal is kept in `localStorage` (`moso-fundraising-bar`) for 7 days and ends early when the milestone changes: before the opening, from the opening, and the last 14 days. An inline head script reads it before first paint so a dismissed bar is never painted and removed.

## Accessibility
An `<aside aria-label="Pienkeräys">` before the banner, not an alert. Two tab stops (link or links, then the close button, labelled "Sulje ilmoitus"). After closing, focus moves to the wordmark. No animation beyond 0.18s colour and press transitions, which are disabled under `prefers-reduced-motion`. Contrast: text 14.8:1 light and 13.3:1 dark, ghost link 9.7:1 and 6.8:1, primary label 10.6:1 and 6.4:1.

## Header and menu
The bar is sticky at z-index 9000. The sticky nav sits below it (`top: var(--fb-h)`), and the mobile drawer (z-index 10000) covers the bar completely.
