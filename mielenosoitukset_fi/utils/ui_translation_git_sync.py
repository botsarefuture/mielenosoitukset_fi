from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import requests
from flask import current_app, has_app_context

from .ui_translation_catalog import update_catalog_entry


class UiTranslationGitSyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class UiTranslationGitSyncResult:
    status: str
    branch_name: str
    commit_sha: str | None = None
    pr_number: int | None = None
    pr_url: str | None = None
    message: str | None = None
    merge_status: str | None = None
    merge_message: str | None = None


def build_ui_translation_sync_branch_name(locale: str, msgid: str) -> str:
    branch_prefix = "ui-translation"
    if has_app_context():
        branch_prefix = current_app.config.get("UI_TRANSLATION_SYNC_BRANCH_PREFIX", branch_prefix)
    digest = sha256(f"{locale}\0{msgid}".encode("utf-8")).hexdigest()[:10]
    return f"{branch_prefix}/{locale}-{digest}"


def _run_git(repo_path: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_path), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _repo_path() -> Path:
    configured = current_app.config.get("UI_TRANSLATION_SYNC_REPO_PATH")
    if configured:
        return Path(configured)
    return Path(current_app.root_path).parent


def _translations_root_for_repo(repo_path: Path) -> Path:
    return repo_path / "mielenosoitukset_fi" / "translations"


def _remote_name() -> str:
    return current_app.config.get("UI_TRANSLATION_SYNC_REMOTE", "origin")


def _git_identity_name() -> str:
    return current_app.config.get("UI_TRANSLATION_SYNC_GIT_AUTHOR_NAME", "Mielenosoitukset UI Translation Bot")


def _git_identity_email() -> str:
    return current_app.config.get("UI_TRANSLATION_SYNC_GIT_AUTHOR_EMAIL", "translations@mielenosoitukset.fi")


def _github_repo() -> str:
    return (current_app.config.get("UI_TRANSLATION_GITHUB_REPO") or "").strip()


def _github_token() -> str:
    return (current_app.config.get("UI_TRANSLATION_GITHUB_TOKEN") or "").strip()


def _github_api_url() -> str:
    return (current_app.config.get("UI_TRANSLATION_GITHUB_API_URL") or "https://api.github.com").rstrip("/")


def _github_headers() -> dict[str, str]:
    token = _github_token()
    if not token:
        raise UiTranslationGitSyncError("UI translation GitHub token is not configured.")
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _find_existing_open_pr(branch_name: str) -> tuple[int | None, str | None]:
    repo = _github_repo()
    if not repo or not _github_token():
        return None, None
    owner = repo.split("/", 1)[0]
    response = requests.get(
        f"{_github_api_url()}/repos/{repo}/pulls",
        params={"state": "open", "head": f"{owner}:{branch_name}", "base": current_app.config.get("UI_TRANSLATION_SYNC_BASE_BRANCH", "main")},
        headers=_github_headers(),
        timeout=15,
    )
    response.raise_for_status()
    pulls = response.json() or []
    if not pulls:
        return None, None
    return pulls[0]["number"], pulls[0]["html_url"]


def _create_pull_request(branch_name: str, locale: str, msgid: str) -> tuple[int | None, str | None]:
    repo = _github_repo()
    if not repo or not _github_token():
        return None, None

    existing_number, existing_url = _find_existing_open_pr(branch_name)
    if existing_number:
        return existing_number, existing_url

    title = f"Update {locale} UI translation: {msgid[:72]}"
    body = "\n".join(
        [
            "Automated UI translation sync from the admin translation review workflow.",
            "",
            f"- Locale: `{locale}`",
            f"- msgid: `{msgid}`",
        ]
    )
    response = requests.post(
        f"{_github_api_url()}/repos/{repo}/pulls",
        headers=_github_headers(),
        json={
            "title": title,
            "head": branch_name,
            "base": current_app.config.get("UI_TRANSLATION_SYNC_BASE_BRANCH", "main"),
            "body": body,
            "draft": False,
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("number"), payload.get("html_url")


def _auto_merge_enabled() -> bool:
    return bool(current_app.config.get("UI_TRANSLATION_GITHUB_AUTO_MERGE", False))


def _attempt_merge_pull_request(pr_number: int) -> tuple[str, str | None]:
    repo = _github_repo()
    if not repo or not _github_token():
        return "not_configured", "GitHub repository or token is not configured for PR merging."

    merge_method = (current_app.config.get("UI_TRANSLATION_GITHUB_MERGE_METHOD") or "squash").strip().lower()
    if merge_method not in {"merge", "squash", "rebase"}:
        merge_method = "squash"

    response = requests.put(
        f"{_github_api_url()}/repos/{repo}/pulls/{pr_number}/merge",
        headers=_github_headers(),
        json={
            "merge_method": merge_method,
        },
        timeout=15,
    )
    if response.status_code == 200:
        payload = response.json() or {}
        return "merged", payload.get("message") or "Pull request merged successfully."
    if response.status_code in {405, 409, 422}:
        payload = response.json() or {}
        return "merge_blocked", payload.get("message") or "Pull request merge is currently blocked."

    response.raise_for_status()
    return "merge_unknown", None


def sync_ui_translation_to_git(locale: str, msgid: str, translated_text: str) -> UiTranslationGitSyncResult:
    repo_path = _repo_path()
    if not repo_path.exists():
        raise UiTranslationGitSyncError(f"Configured UI translation repo path does not exist: {repo_path}")

    base_branch = current_app.config.get("UI_TRANSLATION_SYNC_BASE_BRANCH", "main")
    branch_name = build_ui_translation_sync_branch_name(locale, msgid)
    remote_name = _remote_name()

    worktree_root = Path(tempfile.mkdtemp(prefix="ui-translation-sync-"))
    try:
        _run_git(repo_path, "fetch", remote_name, base_branch)
        _run_git(repo_path, "worktree", "add", "--detach", str(worktree_root), f"{remote_name}/{base_branch}")
        _run_git(worktree_root, "checkout", "-B", branch_name)
        _run_git(worktree_root, "config", "user.name", _git_identity_name())
        _run_git(worktree_root, "config", "user.email", _git_identity_email())

        update_catalog_entry(
            locale,
            msgid,
            translated_text,
            root=_translations_root_for_repo(worktree_root),
        )

        changed_files = _run_git(
            worktree_root,
            "status",
            "--short",
            "--",
            "mielenosoitukset_fi/translations",
        )
        if not changed_files:
            return UiTranslationGitSyncResult(
                status="noop",
                branch_name=branch_name,
                message="The approved UI translation was already present in the repository catalog.",
            )

        _run_git(worktree_root, "add", "mielenosoitukset_fi/translations")
        _run_git(
            worktree_root,
            "commit",
            "-m",
            f"Update {locale} UI translation for {msgid[:64]}",
        )
        commit_sha = _run_git(worktree_root, "rev-parse", "HEAD")

        try:
            _run_git(worktree_root, "push", "--force-with-lease", remote_name, f"HEAD:{branch_name}")
        except subprocess.CalledProcessError as exc:
            return UiTranslationGitSyncResult(
                status="committed_local_branch",
                branch_name=branch_name,
                commit_sha=commit_sha,
                message=exc.stderr.strip() or exc.stdout.strip() or "Failed to push the sync branch to the remote.",
            )

        pr_number, pr_url = _create_pull_request(branch_name, locale, msgid)
        merge_status = None
        merge_message = None
        if pr_number and _auto_merge_enabled():
            merge_status, merge_message = _attempt_merge_pull_request(pr_number)
        return UiTranslationGitSyncResult(
            status="pr_opened" if pr_number else "branch_pushed",
            branch_name=branch_name,
            commit_sha=commit_sha,
            pr_number=pr_number,
            pr_url=pr_url,
            merge_status=merge_status,
            merge_message=merge_message,
        )
    finally:
        try:
            _run_git(repo_path, "worktree", "remove", "--force", str(worktree_root))
        except Exception:
            shutil.rmtree(worktree_root, ignore_errors=True)
