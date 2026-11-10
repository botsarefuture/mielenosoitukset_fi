# Hero

The standard public page introduction: a centred title, one supporting line and up to two actions on the blue `hero-start` → `hero-mid` → `hero-end` gradient.

**Source:** `static/css/public_hero.css` (`.site-hero`).

## What the consumer supplies
- A heading, an `h1` set in `hero-title`.
- One short lead paragraph, set in `hero-lead`.
- Optionally, one or two `.hero-button` links. The main forward action gets `.primary` (white fill, `hero-on-primary` label).

## Rules
- **No eyebrow or kicker.** Don't put a pill label (`site-hero__eyebrow`, `today-kicker`, `cities-kicker`, `org-label`) above the title. The title opens the hero.
- Width is `min(100% - 2rem, hero-max-width)`, radius `site-hero-radius`, shadow `hero-shadow`. The text column is capped at `hero-copy-width`.
- All copy is white. The lead is white at 90%.
- The faint orange glow at the bottom right is the only place `product-accent` appears in the hero.
- Use one hero per page and never nest cards inside it.
