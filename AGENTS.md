# Agents Guide

This repository often gets help from external agents (human or AI). Follow these rules every time you touch the codebase:

1. **Always update the changelog**  
   - Add an entry to `CHANGELOG.md` for every user-facing change (features, fixes, refactors that matter).  
   - If a change launches immediately, put it under the latest released version. Otherwise, log it under `## UNRELEASED`.  
   - Use concise bullets describing the change and its impact.

2. **Keep user context in mind**  
   - Read the existing code and comments before tweaking anything.  
   - Follow the coding style already used in the file (imports, formatting, docstrings, i18n, etc.).

3. **Prefer incremental commits**  
   - Don’t bundle unrelated fixes.  
   - Explain *why* a change is needed in your commit message (or PR description if that’s where you’re working).

4. **Validate before handing off**  
   - Run relevant tests or lint commands when practical.  
   - If you can’t run something (env not available, command fails, etc.), call that out explicitly for the reviewer.

5. **Communicate limitations clearly**  
   - If you’re unsure about requirements, ask.  
   - If you had to make assumptions, list them in your summary so humans can double-check.

## Mandatory visual acceptance

For changes that can affect rendered UI (including template data, CSS, JS,
translations and shared components), read and use
`.agents/skills/moso-visual-qa/SKILL.md`. Run the review here in the conversation,
not as an extra GitHub test suite. The existing product/admin design standard
wins over generic redesign defaults. Capture the real application and obtain a
separate reviewer agent's **SHIP** for the final source/capture snapshot before
declaring the UI ready. The implementer cannot approve their own output. Every
subsequent UI-affecting fix invalidates SHIP: recapture affected states and get
another independent review. Missing browser/screenshots/reviewer means
**BLOCKED**, never an implied pass. Keep existing relevant tests; do not add a
second CI suite or run the full suite just to perform this visual review.

Sticking to these steps keeps the project history readable and prevents surprises for maintainers. Thanks! 🚀

## Modernization direction

For architecture and migration work, read [the maintainer's modernization context](docs/modernization-context.txt)
and [the initial assessment](docs/modernization-assessment.md) before proposing changes.
The context is guidance, not an approved replacement specification.

- Preserve existing functionality, public URLs where practical, MongoDB data,
  accounts, administrative workflows, accessibility, localization and SEO.
- Inspect the relevant implementation and frontend consumers first. Separate
  verified facts, maintainer decisions, recommendations, open questions and risks.
- Migrate incrementally. Measure performance before attributing limitations to
  Flask or choosing a backend replacement. Go is preferred for evaluation, not
  an approved requirement; React + API + Flask admin is a direction to assess.
- Reuse the existing React foundation. React work also exists in other worktrees:
  see the assessment for the campaign implementation. Absence in this checkout
  does not establish that the project has no React implementation. Check its
  current integration status before creating a competing frontend setup.
- Derive API proposals from real routes, consumers, validation and database
  operations. Document purpose, request/response, authentication, authorization,
  database operations, performance concerns and replaced behavior before
  implementing significant API functionality.
- Verify actual password formats and session behavior; do not assume bcrypt or
  introduce JWT/session sharing by default. Keep current authentication working.
- Significant authentication, database schema, infrastructure, repository
  restructuring and production deployment changes require explicit maintainer
  approval. Examples in the context do not supply that approval. Routine work
  within an already approved scope can proceed.
- Test compatibility and establish rollback before replacing working behavior;
  retire old paths only when safe. Update relevant documentation and changelog.
