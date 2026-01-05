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

Sticking to these steps keeps the project history readable and prevents surprises for maintainers. Thanks! 🚀
