from __future__ import annotations

from datetime import datetime

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.logger import logger
from mielenosoitukset_fi.utils.ui_translation_git_sync import (
    UiTranslationGitSyncError,
    sync_ui_translation_to_git,
)


def run(limit: int = 10):
    db = DatabaseManager().get_instance().get_db()
    proposals = list(
        db.ui_translation_proposals.find(
            {
                "status": "approved",
                "github_sync.status": {"$in": ["queued", "retry"]},
            }
        )
        .sort("reviewed_at", 1)
        .limit(max(1, int(limit)))
    )

    for proposal in proposals:
        proposal_id = proposal.get("_id")
        db.ui_translation_proposals.update_one(
            {"_id": proposal_id},
            {
                "$set": {
                    "github_sync.status": "running",
                    "github_sync.started_at": datetime.utcnow(),
                },
                "$inc": {"github_sync.attempts": 1},
            },
        )
        try:
            result = sync_ui_translation_to_git(
                locale=proposal["locale"],
                msgid=proposal["msgid"],
                translated_text=proposal["proposed_text"],
            )
            db.ui_translation_proposals.update_one(
                {"_id": proposal_id},
                {
                    "$set": {
                        "github_sync.status": result.status,
                        "github_sync.branch_name": result.branch_name,
                        "github_sync.commit_sha": result.commit_sha,
                        "github_sync.pr_number": result.pr_number,
                        "github_sync.pr_url": result.pr_url,
                        "github_sync.last_error": "" if result.status not in {"committed_local_branch"} else (result.message or ""),
                        "github_sync.message": result.message or "",
                        "github_sync.finished_at": datetime.utcnow(),
                    }
                },
            )
        except UiTranslationGitSyncError as exc:
            logger.warning("UI translation sync failed for %s: %s", proposal_id, exc)
            db.ui_translation_proposals.update_one(
                {"_id": proposal_id},
                {
                    "$set": {
                        "github_sync.status": "retry",
                        "github_sync.last_error": str(exc),
                        "github_sync.finished_at": datetime.utcnow(),
                    }
                },
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Unexpected UI translation sync failure for %s", proposal_id)
            db.ui_translation_proposals.update_one(
                {"_id": proposal_id},
                {
                    "$set": {
                        "github_sync.status": "retry",
                        "github_sync.last_error": str(exc),
                        "github_sync.finished_at": datetime.utcnow(),
                    }
                },
            )


def main():
    run()


if __name__ == "__main__":
    main()
