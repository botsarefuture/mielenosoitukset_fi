# Branch Handoff: chore-agent-workflow-hooks

## Scope

- Add a lightweight but enforceable workflow for long-running AI/human collaboration.
- Version hooks in the repository instead of relying on ad hoc local git hook state.
- Keep branch handoffs durable and reviewable.

## Current State

- Added a documented operating model in `docs/agent_operating_model.md`.
- Added `docs/handoffs/README.md` plus branch-scoped handoff generation.
- Added versioned `pre-commit` and `pre-push` hooks in `hooks/`.
- Added helper scripts to create/check handoffs and install the repo hooks.

## Validation

- `bash -n scripts/ensure_agent_handoff.sh scripts/install_agent_hooks.sh hooks/pre-commit hooks/pre-push`
- `git diff --check`

## Open Issues

- Hooks are versioned in the repo, but each clone still needs `./scripts/install_agent_hooks.sh` once to activate them.
- The project-level Codex memory file is intentionally local and not part of this PR.

## Next Steps

- Push this branch and open a small infra PR.
- Merge it once reviewed so future work branches inherit the repo-managed workflow.

## Updated

- 2026-05-12
