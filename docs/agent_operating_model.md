# Agent Operating Model

This repository uses a simple operating model so long-running work stays organized across branches, PRs, and agent sessions.

## Goals

- Keep branch context easy to resume.
- Prevent user-facing changes from bypassing `CHANGELOG.md`.
- Make handoff notes first-class project artifacts instead of scattered chat history.
- Keep hooks lightweight enough that they help without blocking normal work unnecessarily.

## Required Branch Ritual

For every active work branch:

1. Keep a handoff note in `docs/handoffs/`.
2. Update `CHANGELOG.md` for user-facing changes.
3. Leave the branch in a state where the next person can answer:
   - what changed
   - what is still broken
   - what should happen next

## Handoff Files

Branch handoff files live in:

- `docs/handoffs/<branch-name>.md`

Branch names are sanitized for filesystem safety:

- `/` becomes `__`

Example:

- branch `feature/my-work`
- file `docs/handoffs/feature__my-work.md`

Each handoff should contain at least:

- current scope
- current state
- validation run
- open issues / blockers
- next steps

## Hooks

This repo ships versioned hooks in `hooks/`.

- `pre-commit`
  - ensures a branch handoff file exists
  - blocks commits that change user-facing code without touching `CHANGELOG.md`
- `pre-push`
  - ensures a branch handoff file exists before pushing
  - prints the handoff file path so the pusher sees the expected resume note

Hooks are installed with:

```bash
./scripts/install_agent_hooks.sh
```

## Local Memory

Project-specific Codex memory is stored outside the repo in:

- `~/.codex/memories/mielenosoitukset_fi_workflow.md`

That memory is intentionally high-level:

- workflow conventions
- branch hygiene
- where durable handoff notes live

The repo remains the source of truth for branch-specific status.
