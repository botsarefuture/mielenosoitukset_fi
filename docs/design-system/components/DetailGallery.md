# DetailGallery

The event image: a full-width cover button that opens a lightbox `<dialog>`, with paging controls when there is more than one image.

**Source:** `frontend/src/components/detail/DetailGallery.tsx`, styled by `.detail-gallery*` and `.detail-lightbox*` in `public-detail.css`. The preview uses a placeholder image.

## What the consumer supplies
`images[]` (URLs) and the event `title`, used as the alt text and the lightbox label.

## Rules
- The cover keeps the image's own aspect ratio (`object-fit: contain`, up to 530px tall, 400px on mobile) on `product-surface-muted`, with `section-radius` and a `product-border` outline. Never crop a cover.
- The overlay label (*Avaa kuva · 1/3*) is `product-text` on `product-surface` with `tag-radius`.
- Paging uses quiet buttons labelled *Edellinen kuva* and *Seuraava kuva*, with a muted `1 / 3` counter between them.
- The lightbox backdrop is `product-overlay`. Esc and *Sulje* close it and return focus to the cover.
- With no usable images, show a `detail-note` instead.
