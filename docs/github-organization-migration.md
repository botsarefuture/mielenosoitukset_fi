# GitHub organization migration

The repository moves from `botsarefuture/mielenosoitukset_fi` to
`mielenosoitukset-fi/mielenosoitukset_fi`.

Canonical URL: <https://github.com/mielenosoitukset-fi/mielenosoitukset_fi/>

Status: the repository is prepared, the transfer itself has not been performed.
Production and preview servers, credentials, environment variables and deployment
paths are unchanged.

GitHub redirects the old repository location for web pages, `git clone`,
`git fetch` and `git push`, so existing clones and the servers' `origin` remotes
keep resolving. Do not create a new repository or fork at the old path: that
permanently removes the redirects.

## References found in the repository

| Location | Reference | Treatment | Why |
| --- | --- | --- | --- |
| `README.md` | clone URL, issue tracker URL | Updated | Canonical instructions a new contributor copies. |
| `README.md` | DeepWiki notice | Kept | External docs site keyed to the old path; re-index before editing (see below). |
| `roadmap.md` | issues #833, #969, #972 and PR #970 | Updated | Live tracker links in the current delivery plan. |
| `docs/design-system/README.md` | "Taken from … at `6265edb`" | Kept | Records where that snapshot came from; rewriting it would misstate history. |
| `docs/design-system/tokens.json` | `meta.repo`, `meta.ref` | Kept | Provenance of the token extraction. No script reads it; only the design-system README mentions the file. |
| `docs/test-runtime-compatibility.md` | CI run `39733692011` | Kept | Historical evidence for the 2026-10-22 runner failure. |
| `docs/modernization-assessment.md` | PR #989 | Kept | Historical reference. |
| `tests/test_ui_translation_workflow.py` | `UI_TRANSLATION_GITHUB_REPO` fixture | Updated | The fake GitHub API test now names the repository production will point at. |

Nothing else referred to the old owner:

- `.github/workflows/*` uses `github.repository`, `context.repo` and
  `github.event.repository.default_branch`, never a literal owner.
- `scripts/open_pr.sh`, `scripts/setup_preview_environment.sh`,
  `deploy/release_public.sh` and the deploy scripts derive the repository from
  `git remote get-url origin`, so they follow the new owner automatically.
- `config.py` has no owner default for `UI_TRANSLATION_GITHUB_REPO`; the value comes
  from the production `config.yaml` (post-transfer action below).
- `pyproject.toml`, `package.json` and the compose project names use the
  `mielenosoitukset-fi` slug, which already matches the organization.
- No GitHub App manifest, webhook definition, CODEOWNERS file, Pages workflow,
  container registry reference or hardcoded `ghcr.io`/`docker.io` namespace exists
  in the repository.

## CI/CD and the merge queue

`python-tests` (`.github/workflows/tests.yml`) is the only required check of the
`main` ruleset, so it is the only workflow that gained `merge_group`. The job has no
`name:` override, so the check keeps the name `python-tests` for both events and the
ruleset's required check still matches.

Notes on the `merge_group` run:

- The fork guard (`github.event.pull_request.head.repo.full_name !=
  github.repository`) is false for `merge_group`, so `MOSO_CI_RUNS_ON` applies.
  Queue commits are created by GitHub inside this repository, so no untrusted code
  reaches the self-hosted host.
- `concurrency` falls back to `github.ref` (the `gh-readonly-queue/...` ref) and
  `cancel-in-progress` stays false, so a queue run does not cancel the PR run.
- `actions/checkout@v4` checks out `github.sha`, the merge group head.
- `permissions: contents: read` was added so the job does not inherit the
  organization's default workflow token permissions; the job writes nothing.

Deliberately unchanged:

- `pr-preview.yml` is not a required check. Running it for queue commits would spend
  production SSH secrets and build an image nobody reviews. Queue merges still emit
  `pull_request` `closed`, so the existing preview cleanup keeps working.
- `dependency-review.yml` needs a pull request base/head diff and cannot run on a
  merge group commit. Do not make it a required check for the queue.
- `render-changelog.yml` and `production-deploy.yml` are not merge checks.

Enabling the queue, its merge method and the required checks is a repository
settings change and is not part of this preparation.

## Deployment

- `production-deploy.yml` runs on pushes to `main`. Queue merges still push to
  `main`, so release building, release assets (`gh release`), deployment and routing
  activation behave as before.
- Production Flask config, `PRODUCTION_SSH_*` and `PREVIEW_SSH_*`, hosts, domains,
  `mielenosoitus.sock` and `/opt/mielenosoitukset-*` paths stay as they are.
- `deploy/production_deploy.sh` resolves `origin/main`; the host's `origin` still
  points at the old URL and follows GitHub's redirect. The verified host details and
  the required follow-up are in the production host audit below.
- Repository secrets, variables, webhooks and deploy keys stay associated with a
  transferred repository (GitHub documentation). Verify them anyway, because
  organization policy can still block them.

## Production host audit (2026-11-13)

Read-only inspection of `lc-main` (`ssh lc-main-root`), the only active production
host. `miekkaridev.luova.club` is no longer in use, so it was not inspected and is
not part of this plan.

What a production deploy actually does:

- The deploy checkout is `/var/www/mielenosoitukset_fi` (HEAD and
  `.deploy-build-sha` were both `86f42748`). Its `origin` is
  `https://github.com/botsarefuture/mielenosoitukset_fi.git` for fetch and push, with
  no credential helper or `insteadOf` rewrite in that repository's config.
- `production-deploy.yml` SSHes in with the dedicated deploy key, whose forced
  command is `/usr/local/sbin/moso-github-deploy`, identical to
  `deploy/production_ssh_entrypoint.sh`. It accepts only `deploy <sha>` and
  `deploy-routing <sha>`, fetches `origin main` in the checkout, refuses a SHA that is
  not `origin/main`, and runs `deploy/production_deploy.sh` from the requested commit.
  It hardcodes no repository URL.
- `production_deploy.sh` fast-forwards `main`, installs dependencies, reloads
  Gunicorn and calls `deploy/release_public.sh`.
- `release_public.sh` derives `owner/name` from `git remote get-url origin` and passes
  it to `deploy/release_artifacts.py`, which downloads
  `https://github.com/{owner}/{name}/releases/download/release-<sha>/release.json`
  plus the verified `api` and `app.tar.gz` assets.

That download is the only production path that reads the old owner after the
transfer, because the remote still names it. The downloader uses `urlopen`, which
follows redirects, and GitHub redirects repository URLs, so deploys are expected to
keep working unchanged. Updating the remote removes the dependency on the redirect.

Everything else on the host is owner-agnostic or already on the new organization:

- Services: `mielenosoitukset_fi.service` (Gunicorn,
  `WorkingDirectory=/var/www/mielenosoitukset_fi`), `mielenosoitukset-public.service`
  (`/opt/mielenosoitukset-public/current`), `mielenosoitukset-api.service`
  (`/opt/mielenosoitukset-api/current`), `mielenosoitukset-telegram-bot.service` and
  `mastobot.service`, plus the MongoDB backup timers running
  `deploy/backup/mongodb-backup.sh` and a LuovaSec snapshot timer. No unit file or
  drop-in contains a GitHub URL or owner reference.
- No systemd unit, timer, root crontab entry or `/etc/cron.d` file runs `git pull` or
  `git fetch` for this repository. Deployments happen only through the Actions SSH
  path, so the host runs no GitHub webhook receiver that would need reconfiguring.
- `/etc/mielenosoitukset-fi/deploy.env`, `/etc/mielenosoitukset-public/environment`
  and `/etc/mielenosoitukset-api/environment` define no `GITHUB*` variable.
- Production `config.yaml` sets `UI_TRANSLATION_GITHUB_REPO:
  botsarefuture/mielenosoitukset_fi`; only that non-secret value was read.
- The other checkouts on the host already use the organization:
  `mielenosoitukset-telegram-bot` and `mastobot` point at `mielenosoitukset-fi/*`.
  `/var/www/mielenosoitukset_fi_v5` is a stale checkout with the old URL that no unit
  uses.

Server-side changes needed after the transfer (not performed; they need maintainer
approval and server access):

1. Point the deploy checkout at the canonical URL:
   `git -C /var/www/mielenosoitukset_fi remote set-url origin https://github.com/mielenosoitukset-fi/mielenosoitukset_fi.git`,
   then verify with `git ls-remote origin main` before the next deploy. Rollback is
   the old URL, which keeps redirecting.
2. Set `UI_TRANSLATION_GITHUB_REPO` to `mielenosoitukset-fi/mielenosoitukset_fi` in
   `/var/www/mielenosoitukset_fi/config.yaml`; the next deploy's Gunicorn reload
   picks it up. No other production setting changes.
3. Optional cleanup: retire `/var/www/mielenosoitukset_fi_v5`.

## External integrations to check after the transfer

These live outside this repository. The repository only shows that they exist or
that it depends on them; their current configuration cannot be inspected from here.

1. UI translation sync (`mielenosoitukset_fi/utils/ui_translation_git_sync.py`) calls
   `/repos/{UI_TRANSLATION_GITHUB_REPO}/pulls`. Set
   `UI_TRANSLATION_GITHUB_REPO: mielenosoitukset-fi/mielenosoitukset_fi` in the
   production `config.yaml`. `UI_TRANSLATION_GITHUB_TOKEN` must still grant pull
   request write on the organization repository, and its user must have write access
   there; otherwise PR creation fails with 403/404.
2. `UI_TRANSLATION_GITHUB_AUTO_MERGE` then merges into the organization repository.
   Confirm the token's merge method is allowed there and that the ruleset does not
   block it.
3. DeepWiki (linked from the README) indexes the old path. Re-index the new
   repository and update the notice once it answers.
4. The self-hosted runner behind `MOSO_CI_RUNS_ON` (`["self-hosted","moso-ci"]`).
   GitHub's transfer documentation does not say whether repository-level runner
   registrations survive; check and re-register if needed.
5. Repository variable `MOSO_CI_RUNS_ON` and the `production` environment used by the
   deploy jobs, including its protection rules and required reviewers.
6. Webhooks, GitHub Apps and review bots. None are declared in this repository;
   check Settings → Webhooks and the organization's installed apps and bot accounts.
7. Dependabot: `.github/dependabot.yml` needs no change, but the organization policy
   must allow Dependabot alerts and version updates.
8. GitHub Pages, if one exists for this repository: Pages URLs are not redirected by
   a transfer.

## Organization settings after the transfer

- Actions: allowed actions (the workflows use `actions/*`, `docker/*` and
  `webfactory/ssh-agent`), default `GITHUB_TOKEN` permissions, self-hosted runner
  policy, and the repository variables and secrets.
- The deploy workflow requests `contents: write` to create release assets; confirm
  organization policy does not block it.
- Rulesets: recreate or verify `main` with the `python-tests` required check and
  resolved review threads, then enable the merge queue with merge commits, matching
  the existing history.
- Environments: restore `production` with its reviewers.
- Members: keep the maintainer as admin; GitHub adds the previous owner as a
  collaborator.
- Security: secret scanning, code scanning and Dependabot alerts at organization
  level, plus the base repository permission for members.

## Post-transfer verification

1. `git remote -v` in each clone and worktree; clone the canonical URL once.
2. `git ls-remote` the old and new URLs; both resolve while redirects exist.
3. Open a throwaway PR: `python-tests` runs, and no workflow fails on a missing
   secret or variable.
4. Inventory secrets, variables, environments and rulesets; compare with the list in
   `docs/production-deployment.md`.
5. Enable the merge queue on a small PR and confirm the queue run reports
   `python-tests` and the PR merges as a merge commit.
6. Watch the first normal push to `main` through release, deploy and routing.
7. Preview: open one PR and confirm the preview comment and cleanup still work.
8. Update `UI_TRANSLATION_GITHUB_REPO` on the servers, run one translation sync, and
   check the PR target.
9. Re-index DeepWiki and fix the README notice.
10. On the production host, set the checkout's `origin` to the canonical URL and
    verify `git ls-remote origin main` before the next deploy.
11. Watch the next deploy: the `downloading release assets … from <slug>` line must
    name `mielenosoitukset-fi/mielenosoitukset_fi`.
12. Remove this document's steps that no longer apply.

## Open risks

- Until the transfer, the README points at a URL that does not exist yet.
- Redirects disappear if a repository is created at the old path.
- GitHub retires an old owner/name combination once a transferred repository had more
  than 100 clones or 100 Actions uses in the prior week. Redirects for web and git
  traffic still apply, but do not rely on the old API paths long term.
- Transfer behaviour for repository-level self-hosted runners, environments and
  rulesets is not documented; verify each instead of assuming it moved.
- Anything outside the repository (bots, webhooks, dashboards) in the list above is
  unverified by this audit.
- Until the production remote is updated, the release asset download depends on
  GitHub's repository redirect. If that redirect ever stops working, a deploy would
  reload Flask and then fail before the public host and Go API, which is the
  half-deployed state the script otherwise avoids.
