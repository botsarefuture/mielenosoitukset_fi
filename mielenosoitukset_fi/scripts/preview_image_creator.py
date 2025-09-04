"""
Create preview images for demonstrations with progress meter.
"""

import os
import io
from flask import has_app_context
from flask import current_app

from DatabaseManager import DatabaseManager
from mielenosoitukset_fi.utils.screenshot import create_screenshot, trigger_screenshot
from mielenosoitukset_fi.utils.s3 import upload_image_fileobj
from config import Config
from mielenosoitukset_fi.utils.logger import logger

from tqdm import tqdm  # progress bar

def run(force=False):
    """
    Create preview images for demonstrations with progress feedback.
    """
    
    if not has_app_context():
        logger.error("No Flask application context found.")
        return

    db_man = DatabaseManager().get_instance()
    mongo = db_man.get_db()  # Get the MongoDB Database instance

    demos = mongo["demonstrations"]

    # Fetch demos
    if force:
        all_demos = list(demos.find({}))
    else:
        all_demos = list(demos.find({"in_past": False}))

    total = len(all_demos)
    logger.info(f"Processing {total} demonstrations...")

    for demo in tqdm(all_demos, desc="Creating previews", unit="demo"):
        demo_dict = demo
        demo_id = demo_dict.get("_id")

        # Skip if preview already exists and not forcing
        if not force and demo_dict.get("preview_image"):
            continue

        png_bytes = create_screenshot(demo_dict, return_bytes=True)
        if not png_bytes:
            logger.warning(f"Failed to render screenshot for demo {demo_id}")
            continue

        bucket_name = getattr(Config, "S3_BUCKET", "mielenosoitukset.fi")
        fileobj = io.BytesIO(png_bytes)
        s3_url = upload_image_fileobj(bucket_name, fileobj, f"{str(demo_id)}.png", "demo_preview")

        if s3_url:
            try:
                demos.update_one({"_id": demo_id}, {"$set": {"preview_image": s3_url}})
                logger.info(f"Uploaded preview image for demo {demo_id} to {s3_url}")
            except Exception as e:
                logger.error(f"Uploaded but failed to update DB for demo {demo_id}: {e}")
        else:
            logger.error(f"Failed to upload preview image for demo {demo_id} to S3")
        
    logger.info("All screenshots created.")
