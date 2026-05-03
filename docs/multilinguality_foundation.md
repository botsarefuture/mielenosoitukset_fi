# Multilinguality Foundation

This branch starts the data-model groundwork for full multilingual demonstrations.

## Current decisions

- Demo translations live under `demonstrations.translations`.
- The structure is language-first:

```json
{
  "default_language": "fi",
  "translations": {
    "en": {
      "title": "English title",
      "description": "English description",
      "tags": ["peace", "march"]
    },
    "sv": {
      "title": "Svensk titel"
    }
  }
}
```

- Base fields stay in place for backwards compatibility:
  - `title`
  - `description`
  - `tags`
- `default_language` tells which language the base fields are authored in.
- Missing translations must fall back to the base field values.

## Why this shape

- It avoids breaking every existing query, page, email, and API path immediately.
- It lets us introduce multilinguality incrementally.
- It keeps the default/public language explicit instead of assuming everything is always Finnish forever.

## What this branch adds

- `Demonstration.translations`
- `Demonstration.default_language`
- helper methods:
  - `set_translation(language, field, value)`
  - `get_translation(language, field, fallback=True)`
  - `get_localized_fields(language, fallback=True)`
  - `available_translation_languages()`
- shared utility helpers:
  - `get_demo_localized_value(demo, field, language=None, fallback=True)`
  - `get_demo_localized_fields(demo, language=None, fallback=True)`

Those helpers are intentionally backward-compatible:
- they use translated content when it exists for the requested language
- they fall back to the legacy base fields when it does not
- they work for both `Demonstration` objects and plain demo dictionaries

The first public UI slice is also now in place:
- demo detail rendering resolves localized `title`, `description`, and `tags`
- calendar views resolve localized demo titles/descriptions/tags from the active locale
- API/card-format demo payloads use the same localization helper path

The first admin UI slice is now in place too:
- admin demo create/edit form exposes `default_language`
- admin demo create/edit form stores translated `title`, `description`, and `tags`
- edit views prefill saved translations back into the form

The next admin/public slice is now also in place:
- recurring demo create/edit form exposes `default_language`
- recurring demo create/edit form stores translated `title`, `description`, and `tags`
- public submit flow stores the authored language of the base fields through `default_language`
- public submit still does not expose per-locale translation editors; that remains a later UX decision

## Next implementation slices

1. Public rendering
- read localized title/description/tags based on session locale
- keep fallback to base fields

2. Admin UI
- add translation editors for title/description/tags
- show which locales are missing

3. Public submit flow
- decide whether normal submit creates only the base language entry
- add optional translation inputs later, not in the first migration

4. Search and feeds
- decide whether search matches only base fields or translated fields too
- update RSS, cards, detail views, and sitemap output

5. Notifications and emails
- ensure submitter/admin emails use the recipient locale where possible

## Open questions

- Should address be translatable too, or only title/description/tags?
- Should recurring demos share the same translation structure?
- Should the API expose one localized view or the full translation map?
