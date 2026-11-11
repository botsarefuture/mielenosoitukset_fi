import argparse
import os
import io
import tempfile
from flask import current_app, has_app_context
from bson import ObjectId

from mielenosoitukset_fi.database_manager import DatabaseManager

from mielenosoitukset_fi.utils.logger import logger
from mielenosoitukset_fi.utils.preview_image import render_preview_png

# Kept from the wkhtmltoimage renderer, which no longer needs it. Importing this
# module points XDG_CACHE_HOME at an empty directory, so on Linux Playwright no
# longer finds its browser and the test suite skips every browser test. Removing
# these lines re-enables those tests, some of which currently fail on main; do
# that in its own change together with fixing them.
os.environ["XDG_CACHE_HOME"] = tempfile.mkdtemp()
os.environ["XDG_RUNTIME_DIR"] = tempfile.mkdtemp()

save_path = os.environ.get("demo_image_save_path", "/var/www/mielenosoitukset_fi/mielenosoitukset_fi/static/demo_preview")


def create_screenshot(demo_data, output_path=save_path, return_bytes=False):
    """
    Render the 1200×630 social preview image for a demonstration.

    The image is drawn with Pillow by
    :func:`mielenosoitukset_fi.utils.preview_image.render_preview_png`; no
    browser or network access is needed.

    Parameters
    ----------
    demo_data : dict or Demonstration
        The demonstration to render.
    output_path : str, optional
        Directory path where the PNG will be saved if return_bytes is False.
    return_bytes : bool, optional
        If True, return PNG bytes instead of writing to disk.

    Returns
    -------
    str or bytes or None
        If return_bytes is False: returns the relative static path (e.g. '/static/demo_preview/{id}.png') or None on failure.
        If return_bytes is True: returns PNG bytes or None on failure.
    """
    try:
        if not isinstance(demo_data, dict):
            if hasattr(demo_data, "to_dict"):
                demo_data = demo_data.to_dict(True)
            else:
                raise ValueError("Invalid demonstration data provided.")

        filename = f"{demo_data['_id']}.png"

        if not return_bytes:
            os.makedirs(output_path, exist_ok=True)
            full_path = os.path.join(output_path, filename)
            if os.path.exists(full_path):
                return f"/static/demo_preview/{filename}"

        png_bytes = render_preview_png(demo_data)

        if return_bytes:
            logger.info(f"Preview image rendered to bytes for: {demo_data['_id']}")
            return png_bytes

        with open(full_path, "wb") as handle:
            handle.write(png_bytes)
        logger.info(f"Preview image created at: {full_path}")
        return full_path.replace("/var/www/mielenosoitukset_fi/mielenosoitukset_fi/", "").replace("../", "/")

    except Exception as e:
        logger.error(f"Failed to create preview image: {e}")
        return None

import threading

def trigger_screenshot(demo_id, wait=False, force=False):
    """
    Trigger the creation of a screenshot for a given demonstration ID and upload to S3.

    Parameters
    ----------
    demo_id : str
        The ID of the demonstration.
    wait : bool
        If True, block until the screenshot is done.
    force : bool
        If True, regenerate even when a preview already exists.

    Returns
    -------
    bool, str
        True/False for success, message.
    """
    def create_screenshot_thread(demo_id, force_generate):
        from mielenosoitukset_fi.utils.classes.Demonstration import Demonstration
        from mielenosoitukset_fi.utils.s3 import upload_image_fileobj
        from config import Config

        try:
            db_man = DatabaseManager().get_instance()
            mongo = db_man.get_db()
            data = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
            if not data:
                logger.error(f"No demonstration found with ID {demo_id}")
                return
            if data.get("preview_image") and not force_generate:
                logger.info(f"Preview already exists for demo {demo_id}; skipping screenshot generation.")
                return

            demo = Demonstration.from_dict(data)

            # Render screenshot bytes inside app context
            try:
                with current_app.app_context():
                    png_bytes = create_screenshot(demo, return_bytes=True)
            except Exception as e:
                logger.error(f"Failed to render screenshot for {demo_id}: {e}")
                return

            if not png_bytes:
                logger.error(f"No screenshot bytes produced for demo {demo_id}")
                return

            # Upload to S3
            try:
                bucket_name = getattr(Config, "S3_BUCKET", "mielenosoitukset.fi")
                fileobj = io.BytesIO(png_bytes)
                fileobj.seek(0)
                s3_url = upload_image_fileobj(
                    bucket_name,
                    fileobj,
                    f"{str(demo_id)}.png",
                    "demo_preview"
                )
                if not s3_url:
                    logger.error(f"Failed to upload preview image for demo {demo_id} to S3")
                    return
                logger.info(f"Uploaded preview for demo {demo_id} -> {s3_url}")
            except Exception as e:
                logger.error(f"Exception during S3 upload for {demo_id}: {e}")
                return

            # Update DB record
            try:
                mongo.demonstrations.update_one({"_id": ObjectId(demo_id)}, {"$set": {"preview_image": s3_url}})
                logger.info(f"Database updated with preview URL for demo {demo_id}")
            except Exception as e:
                logger.error(f"Uploaded preview but failed to update DB for demo {demo_id}: {e}")
                return

        except Exception as e:
            logger.error(f"Exception in screenshot thread: {e}")

    # Capture the Flask application object so the worker thread can push
    # an application context. Prefer the current app if running inside an
    # app context; otherwise try to create one (best-effort fallback).
    app = None
    created_app = None
    if has_app_context():
        # Prefer the real Flask app when running inside a context. Use
        # getattr to avoid static-analysis errors about LocalProxy internals.
        try:
            app = getattr(current_app, "_get_current_object")()
        except Exception:
            app = current_app
    else:
        try:
            # Import here to avoid circular imports at module import time
            from mielenosoitukset_fi.app import create_app

            created_app = create_app()
            app = created_app
            logger.info("Created a temporary Flask app for screenshot threading.")
        except Exception as e:
            logger.error(f"No Flask application context available and auto-create failed: {e}")
            return False, "No Flask application context available."

    try:
        def runner(demo_id):
            try:
                # Ensure the worker has a proper application context
                with app.app_context():
                    create_screenshot_thread(demo_id, force)
            except Exception as e:
                logger.error(f"Exception in screenshot runner thread: {e}")

        thread = threading.Thread(target=runner, args=(demo_id,))
        thread.daemon = True  # Won't block app shutdown
        thread.start()

        if wait:
            thread.join()

        return True, "Screenshot thread started successfully"
    except Exception as e:
        logger.error(f"Failed to trigger screenshot thread: {e}")
        return False, f"Failed to trigger screenshot thread: {e}"


def main():
    parser = argparse.ArgumentParser(description="Create a screenshot for a demonstration.")
    parser.add_argument("demo_id", type=str, help="The ID of the demonstration.")
    parser.add_argument("--wait", action="store_true", help="Wait for the screenshot to be created.")
    args = parser.parse_args()

    success, _ = trigger_screenshot(args.demo_id, args.wait)
    if success:
        print("Screenshot creation triggered successfully.")
    else:
        print("Failed to trigger screenshot creation.")

if __name__ == "__main__":
    main()
