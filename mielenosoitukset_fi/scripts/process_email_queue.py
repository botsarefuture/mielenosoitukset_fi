"""
Drain the email_queue for queued emails that may have been orphaned.

This script processes emails from the email_queue collection directly,
ensuring delivery even when the originating EmailSender instance has been
destroyed (e.g., during process restarts or script exits).

Run periodically via the scheduler to guarantee queued emails are sent.
"""
from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.emailer.EmailJob import EmailJob
from mielenosoitukset_fi.emailer.EmailSender import EmailSender
from mielenosoitukset_fi.utils.logger import logger
from config import Config

# Reuse one sender for SMTP settings without spawning the per-instance
# worker thread: this script drains the queue itself.
_sender_config = Config()
setattr(_sender_config, "ENABLE_EMAIL_WORKER", False)
_sender = EmailSender(_sender_config)


def run(max_jobs: int = 50):
    """Process queued email jobs from the database.

    Parameters
    ----------
    max_jobs : int, optional
        Maximum number of jobs to process per run. Defaults to 50.

    This drains the entire email_queue collection without filtering by
    instance_id, ensuring jobs are sent even if the queuing process has
    exited or restarted.
    """
    db = DatabaseManager().get_instance().get_db()
    queue = db["email_queue"]
    processed = 0

    while processed < max_jobs:
        job_doc = queue.find_one_and_delete({}, sort=[("_id", 1)])
        if not job_doc:
            break

        try:
            email_job = EmailJob.from_dict(job_doc)
            _sender.send_email(email_job, raise_on_error=True)
            processed += 1
        except Exception:
            logger.exception("Failed to process email job %s", job_doc.get("_id"))

    if processed:
        logger.info("Processed %d queued email jobs.", processed)
    return processed


if __name__ == "__main__":
    run()