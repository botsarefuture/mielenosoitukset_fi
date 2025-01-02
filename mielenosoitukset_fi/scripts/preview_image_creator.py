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
from mielenosoitukset_fi.utils.screenshot import trigger_screenshot

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
            
        result = trigger_screenshot(demo._id, True) # Trigger the screenshot creation for the demonstration
        if result:
            logger.info(f"Screenshot created for demonstration: {demo._id}")
        
        else:
            logger.warning(f"Failed to create screenshot for demonstration: {demo._id}")
            
        if demo.img is None:
            demo.preview_image = '/static/demo_preview/' + str(demo._id) + '.png'
            demo.save()
        
    logger.info("All screenshots created.") # Print a message when all screenshots have been created