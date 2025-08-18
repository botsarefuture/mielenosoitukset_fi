"""
Create preview images for demonstrations.

This script is used for creating preview images for the demonstrations,
regularly updated on the website.
"""

import os

from flask import has_app_context
from flask import current_app

from DatabaseManager import DatabaseManager

from mielenosoitukset_fi.utils.classes import Demonstration
from mielenosoitukset_fi.utils.screenshot import trigger_screenshot, save_path
from mielenosoitukset_fi.utils.s3 import upload_image

from mielenosoitukset_fi.utils.logger import logger

def run():
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

    all_demos = list(demos.find({"in_past": False})) # Get all demonstrations that are not in the past

    for demo in all_demos:
        demo = Demonstration.from_dict(demo) # Convert the dictionary to a Demonstration object
        if demo.preview_image: # If the demonstration does not have a preview image
            continue
            
        result = trigger_screenshot(demo._id, True)  # Trigger the screenshot creation for the demonstration
        if result:
            logger.info(f"Screenshot created for demonstration: {demo._id}")
        else:
            logger.warning(f"Failed to create screenshot for demonstration: {demo._id}")

        # Determine the file that should have been created
        local_file = os.path.join(save_path, f"{demo._id}.png")
        if os.path.exists(local_file):
            # Upload to S3 and set the CDN URL as preview_image
            bucket_name = "mielenosoitukset.fi"
            s3_url = upload_image(bucket_name, local_file, "demo_preview")
            if s3_url:
                demo.preview_image = s3_url
                demo.save()
                try:
                    os.remove(local_file)
                except Exception:
                    logger.debug(f"Could not remove local preview file: {local_file}")
            else:
                logger.error(f"Failed to upload preview image for demo {demo._id} to S3")
        else:
            logger.warning(f"Expected preview image not found at {local_file} for demo {demo._id}")
        
    logger.info("All screenshots created.") # Print a message when all screenshots have been created