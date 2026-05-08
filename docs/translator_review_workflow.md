# Translator Review Workflow

This branch adds the first reviewable translator workflow for demonstration translations.

## What exists now

- A new global role: `translator`
- An implied translator permission: `TRANSLATE_DEMO`
- A dedicated admin-side translation queue: `/admin/demo/translations`
- A dedicated translation editor per demonstration: `/admin/demo/<demo_id>/translations`
- Review actions for admins:
  - approve proposal
  - reject proposal

## Current data model

Demonstrations may now contain:

- `default_language`
- `translations.<locale>`
- `translation_proposals.<locale>`

Example:

```json
{
  "default_language": "fi",
  "translations": {
    "en": {
      "title": "Climate March",
      "description": "Approved English version",
      "tags": ["climate", "march"]
    }
  },
  "translation_proposals": {
    "en": {
      "language": "en",
      "title": "Climate March",
      "description": "Pending English proposal",
      "tags": ["climate", "march"],
      "status": "pending",
      "submitted_by": "...",
      "submitted_by_name": "Translator User",
      "submitted_at": "..."
    }
  }
}
```

## Intentional limits in this first slice

- This workflow currently covers normal demonstrations only.
- Recurring-demo translation review still needs a matching workflow.
- Public rendering does not yet consume approved translations from this branch.
- There is no separate `moderator` role yet; review is handled by admin/global admin.

## Recommended next slices

1. Add recurring-demo translation proposals and review.
2. Make public demo rendering locale-aware based on approved `translations`.
3. Add reviewer notes/history UI to the queue list itself.
4. Add notifications:
   - translator notified on approval/rejection
   - reviewer notified about new pending proposals
5. Decide whether admin demo editing should also expose direct translation editing, or whether proposal-only should remain the only path.
