# Admin UI Visual Style

This guide documents the visual language used by the refreshed admin user, organization, suggestion, and analytics pages. New admin views should feel calm, practical, and friendly rather than looking like a generic dashboard template.

## Design Principles

- **Content first.** Use hierarchy, spacing, and short labels before adding decoration.
- **Calm, not sterile.** Blue carries structure and trust; orange is a small warm accent.
- **Useful cards only.** A card should group related work or summarize a meaningful fact.
- **Dark mode is a first-class theme.** Every surface, control, border, modal, and state must remain readable in both themes.
- **Responsive by default.** Dense tables may scroll horizontally, while page-level grids should collapse cleanly.

## Page Anatomy

Use these elements when they fit the page:

1. A blue gradient hero with a short uppercase kicker, one clear heading, concise supporting copy, and a small group of contextual actions.
2. A summary row of two to four compact metric cards.
3. White or dark themed work cards with muted headers and clear section titles.
4. Tables with quiet borders, uppercase column labels, recognizable identity cells, and grouped row actions.
5. Friendly empty states that explain what is missing and what can be done next.
6. Longer edit forms split into focused cards with a responsive side guide and a sticky save bar.

Avoid long instructional paragraphs at the top of operational pages. Put help near the action it explains.

## Tokens

Admin pages currently define scoped CSS custom properties because the refreshed visual system is being adopted incrementally:

```css
--admin-blue: light-dark(#0033a0, #8bb1ff);
--admin-blue-dark: light-dark(#00267a, #c5d6ff);
--admin-blue-soft: light-dark(#edf4ff, #17233b);
--admin-orange: #ff6600;
--admin-orange-soft: light-dark(#fff2e8, #3a2418);
--admin-surface: light-dark(#ffffff, #20252d);
--admin-surface-muted: light-dark(#f6f8fb, #292f39);
--admin-border: light-dark(#dce3ec, #424b59);
--admin-text: light-dark(#172033, #f2f5fa);
--admin-muted: light-dark(#647083, #b7c0ce);
```

Page-specific prefixes such as `--orgs-*` or `--users-*` are acceptable until these tokens move into the shared admin stylesheet.

## Shape And Spacing

- Hero radius: `1.5rem`
- Main card radius: about `1rem`
- Button and control radius: `.65rem` to `.75rem`
- Page and card gap: about `1rem`
- Use subtle borders and restrained shadows. Avoid glowing borders, glass effects, and gradients outside the hero.

## Type And Icons

- Keep headings bold with slightly tight letter spacing.
- Use compact uppercase kickers and table headers sparingly.
- Pair icons with text when they improve recognition; icons should sit in small tinted tiles for summary cards and facts.
- Prefer existing Font Awesome icons and keep icon choices literal.

## Actions And Feedback

- Primary actions use solid blue with white text.
- Secondary actions use a muted surface and border.
- Orange is for attention or unusual-but-safe actions.
- Destructive actions use a soft red surface and explicit confirmation.
- Use themed modals and inline toasts for workflow feedback instead of browser `alert()` dialogs.
- Disable controls while their request is running and show a clear success or error result.
- Keep primary save controls easy to reach on long forms with a restrained sticky save bar.

## Reference Implementations

- `templates/admin_V2/user/list.html`
- `templates/admin_V2/organizations/dashboard.html`
- `templates/admin_V2/organizations/view.html`
- `templates/admin_V2/organizations/form.html`
- `templates/admin_V2/analytics.html`
