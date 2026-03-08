"""
Generate and upload preview images for demonstrations.

This script queries demonstration records from the MongoDB database,
creates preview images (screenshots), uploads them to S3, and updates
the database records with the generated preview URLs.

It supports optional force-regeneration and limiting the demonstrations
processed to a given number of days into the future.
"""

import io
from datetime import datetime, timedelta
from flask import has_app_context

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.screenshot import create_screenshot
from mielenosoitukset_fi.utils.s3 import upload_image_fileobj
from config import Config
from mielenosoitukset_fi.utils.logger import logger

from tqdm import tqdm  # for progress visualization


def run(force: bool = False, till: int = 0) -> None:
    """
    Create preview images for demonstrations with progress feedback.

    Workflow:
        1. Query demonstrations from MongoDB.
        2. Optionally filter by upcoming events within `till` days.
        3. Generate screenshot previews for demonstrations without one
           (or all if `force=True`).
        4. Upload previews to S3 and update demonstration records.

    Parameters
    ----------
    force : bool, default=False
        If True, regenerate previews for *all* demonstrations,
        even if a preview already exists.
        If False, only demonstrations without a preview will be processed.
    
    till : int, default=0
        Number of days from today to limit demonstrations.
        - 0  = no time limit (all demos).
        - >0 = include only demonstrations scheduled up to `till` days in the future.

    Returns
    -------
    None
        Logs progress, successes, and errors.
    """

    # Ensure we have a Flask application context
    if not has_app_context():
        logger.error("No Flask application context found. Aborting preview generation.")
        return

    # Initialize database connection
    db_man = DatabaseManager().get_instance()
    mongo = db_man.get_db()
    demos = mongo["demonstrations"]

    # -------------------------------
    # Build query for demonstration selection
    # -------------------------------
    query = {}
    if not force:
        # By default, skip past demonstrations
        query["in_past"] = False

    if till and till > 0:
        cutoff_date = datetime.now() + timedelta(days=till)
        # Ensure compatibility with stored date type
        query["date"] = {"$lte": str(cutoff_date.date())}
        logger.info(f"Limiting to demonstrations scheduled until {cutoff_date.date()}")

    # -------------------------------
    # Fetch demonstrations
    # -------------------------------
    all_demos = list(demos.find(query))
    total = len(all_demos)
    logger.info(f"Found {total} demonstrations (force={force}, till={till}).")

    if total == 0:
        logger.info("No demonstrations to process. Exiting.")
        return

    # -------------------------------
    # Process each demonstration
    # -------------------------------
    for demo in tqdm(all_demos, desc="Creating previews", unit="demo", total=total):
        demo_id = demo.get("_id")

        # Skip if preview already exists (unless forcing regeneration)
        if not force and demo.get("preview_image"):
            continue

        # Generate screenshot as bytes
        png_bytes = create_screenshot(demo, return_bytes=True)
        if not png_bytes:
            logger.warning(f"Failed to render screenshot for demo {demo_id}")
            continue
        # Upload preview to S3
        bucket_name = getattr(Config, "S3_BUCKET", "mielenosoitukset.fi")
        fileobj = io.BytesIO(png_bytes)
        s3_url = upload_image_fileobj(
            bucket_name,
            fileobj,
            f"{str(demo_id)}.png",
            "demo_preview"
        )

        # Update database record if upload succeeded
        if s3_url:
            try:
                demos.update_one({"_id": demo_id}, {"$set": {"preview_image": s3_url}})
                logger.info(f"Uploaded preview for demo {demo_id} -> {s3_url}")
            except Exception as e:
                logger.error(f"Uploaded preview but failed to update DB for demo {demo_id}: {e}")
        else:
            logger.error(f"Failed to upload preview image for demo {demo_id} to S3")

    logger.info("Preview generation completed successfully.")
