# ContactOption

A tappable card for one way to get in touch or continue, with an icon chip, a bold title and a one-line value; cards sit in a grid that stacks on narrow screens.

**Source:** `.contact-options` and `.contact-option` in `frontend/src/app/information/information.css`, used by `ContactScreen.tsx` (`/contact`) and `information/AboutContent.tsx` (`/info`).

## What the consumer supplies
A link target (`mailto:`, a page or an in-page anchor), a Font Awesome icon (`aria-hidden`), a short Finnish title (*Sähköposti*, *Yhteydenottolomake*) and the value or one-line description (*tuki@mielenosoitukset.fi*, *Lähetä viesti suoraan*).

## Rules
- The card is a link on `product-surface-muted` with a `product-border` outline, 12px radius and at least `touch-target` height. Hover changes the outline to `product-primary`.
- The icon chip is 2.5rem on `product-primary-soft` with a `product-primary` glyph and 8px radius.
- The title is bold `product-primary`; the value line is regular `product-text` and may wrap anywhere (long email addresses).
- Focus is a 3px `product-primary` outline with a 3px offset.
- `.contact-options` is an auto-fit grid of at least 16rem columns; add `.contact-options--stacked` in a narrow column to keep one card per row.
- Only link to something that works now: hide an option when its target is unavailable, such as the form card while the contact form is switched off.
