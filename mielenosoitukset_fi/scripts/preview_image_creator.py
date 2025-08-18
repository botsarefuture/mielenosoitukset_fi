"""
Create preview images for demonstrations.

This script is used for creating preview images for the demonstrations,
regularly updated on the website.
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

def run(force=False):
    """
    Create preview images for demonstrations.
    """
    
    if not has_app_context():
        logger.error("No Flask application context found.")
        return

    db_man = DatabaseManager().get_instance()

    mongo = db_man.get_db() # Get the MongoDB Database instance

    # Get the collection of demonstrations
    demos = mongo["demonstrations"]

    # If force is True, process all demonstrations (including past ones)
    if force:
        all_demos = list(demos.find({}))
    else:
        all_demos = list(demos.find({"in_past": False}))  # Get all demonstrations that are not in the past

    for demo in all_demos:
        # Work with the raw document from Mongo to avoid conversion errors
        demo_dict = demo
        demo_id = demo_dict.get("_id")

        # If not forcing, skip demos that already have a preview image
        if not force and demo_dict.get("preview_image"):
            continue

        # Render screenshot to bytes in-memory
        png_bytes = create_screenshot(demo_dict, return_bytes=True)
        if not png_bytes:
            logger.warning(f"Failed to render screenshot for demo {demo_id}")
            continue

        bucket_name = getattr(Config, "S3_BUCKET", "mielenosoitukset.fi")
        # upload_image_fileobj expects a file-like object; wrap bytes in BytesIO
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
        
    logger.info("All screenshots created.") # Print a message when all screenshots have been created