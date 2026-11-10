# Badge

A small uppercase status pill at the top of a demonstration card.

**Source:** `.demo-badge` in `static/css/user-workspace.css`.

## Variants
- `.today-badge` (`badge-today`): the event is today. ⚠ White text on it is only 3.1:1. That is the source's value, kept as is. The label is a word, so meaning never relies on colour alone.
- `.cancelled-badge` (`badge-cancelled`): the event is cancelled (*Peruttu*).
- `.pride-badge`: `product-text` on solid `product-surface` (16.3:1 light, 14.1:1 dark), with a 2px `product-pride-gradient` rainbow border. Never place its text over the gradient.
- Default: a `product-text-muted` fill. ⚠ In the dark theme, white on `#b7c0ce` is 1.8:1. Prefer a named variant there.

## Rules
Set the text in the `badge` style on a `radius-pill`. The text must be a word. Never rely on colour alone, and never show more than three badges on one card.
