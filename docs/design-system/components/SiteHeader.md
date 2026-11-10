# SiteHeader

The public top bar and main navigation: the text wordmark on the action-blue gradient, an optional outlined header link and the FI/SV/EN switcher, with a white nav bar below it.

**Source:** `frontend/src/components/header/SiteHeader.tsx`, styled by `static/css/public-header.css`. This is a static rendition of that markup.

## What the consumer supplies
- `brand` (always `Mielenosoitukset.fi`) and the `home` URL.
- Navigation items. Each one has a Font Awesome icon and a Finnish label, for example *Tulevat mielenosoitukset*, *Kaupungit*, *Ilmoita mielenosoituksesta*, *Kirjaudu sisään*.
- The current locale. Its language button gets `.active`.

## Rules
- The bar is `linear-gradient(135deg, product-action-bg, product-action-hover)`. Everything on it is `product-on-action`.
- The active nav link gets `.active` (a 3px `product-primary` underline) and `aria-current="page"`.
- Every control is at least `touch-target` (44px) tall on mobile. Focus outlines are 2px, in `product-on-action` on the bar and `product-primary` on the nav.
- The wordmark is plain type, the `logo` style. Never replace it with an image.
