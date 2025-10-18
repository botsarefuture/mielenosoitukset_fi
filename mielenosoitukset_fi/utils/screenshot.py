from jinja2 import Environment, FileSystemLoader, select_autoescape
import argparse
import os
import tempfile
import threading
import io
from flask import current_app, has_app_context, render_template, url_for
import imgkit

from mielenosoitukset_fi.utils.logger import logger
from mielenosoitukset_fi.utils import _CUR_DIR
from mielenosoitukset_fi.utils.classes.Demonstration import Demonstration

# Set XDG_CACHE_HOME to a writable directory
os.environ["XDG_CACHE_HOME"] = tempfile.mkdtemp()
# Set XDG_RUNTIME_DIR to a writable directory
os.environ["XDG_RUNTIME_DIR"] = tempfile.mkdtemp()
config = imgkit.config()

save_path = os.environ.get("demo_image_save_path", "/var/www/mielenosoitukset_fi/mielenosoitukset_fi/static/demo_preview")


def create_screenshot(demo_data, output_path=save_path, return_bytes=False):
    """
    Create a PNG screenshot from the preview template.

    Parameters
    ----------
    demo_data : dict
        Dictionary containing the demonstration data.
    output_path : str, optional
        Directory path where the screenshot PNG will be saved if return_bytes is False.
    return_bytes : bool, optional
        If True, return PNG bytes instead of writing to disk.

    Returns
    -------
    str or bytes or None
        If return_bytes is False: returns the relative static path (e.g. '/static/demo_preview/{id}.png') or None on failure.
        If return_bytes is True: returns PNG bytes or None on failure.
    """
    try:
        # Ensure we have a Flask application context. If none exists (e.g. running
        # from a script), try to create one from the application's factory.
        app_ctx = None
        created_app = None
        if not has_app_context():
            try:
                # Import here to avoid circular imports at module import time
                from mielenosoitukset_fi.app import create_app

                created_app = create_app()
                app_ctx = created_app.app_context()
                app_ctx.push()
                logger.info("Pushed a new Flask app context for screenshot rendering.")
            except Exception as e:
                logger.error(f"Failed to create Flask app context: {e}")
                raise ValueError("No Flask application context found and auto-creation failed.")

        if not isinstance(demo_data, dict):
            if hasattr(demo_data, "to_dict"):
                demo_data = demo_data.to_dict(True)
            else:
                raise ValueError("Invalid demonstration data provided.")

        try:
            # Prepare a copy of the demo data for the template to avoid mutating the source
            demo_for_template = dict(demo_data)
            # Format date to Finnish format DD.MM.YYYY if possible
            try:
                if demo_for_template.get("date"):
                    from datetime import datetime as _dt

                    try:
                        parsed = _dt.strptime(demo_for_template["date"], "%Y-%m-%d")
                        demo_for_template["date"] = parsed.strftime("%d.%m.%Y")
                    except Exception:
                        # leave date as-is if it can't be parsed
                        pass
                # Format start_time and end_time to HH:MM if present
                for tkey in ("start_time", "end_time"):
                    tval = demo_for_template.get(tkey)
                    if tval:
                        try:
                            # Try HH:MM:SS then HH:MM
                            try:
                                parsed_t = _dt.strptime(tval, "%H:%M:%S")
                            except Exception:
                                parsed_t = _dt.strptime(tval, "%H:%M")
                            demo_for_template[tkey] = parsed_t.strftime("%H:%M")
                        except Exception:
                            # leave as-is on failure
                            pass
            except Exception:
                pass

            env = Environment(
                loader=FileSystemLoader(os.path.join(_CUR_DIR, '../templates')),
                autoescape=select_autoescape(['html', 'xml'])
            )
            template = env.get_template("preview.html")
            html_content = template.render(demo=demo_for_template)
        except Exception as e:
            logger.error(f"Failed to render HTML content: {e}")
            return None
        finally:
            # Pop the context if we pushed one earlier. Don't pop if the current
            # running app supplied the context.
            if app_ctx is not None:
                try:
                    app_ctx.pop()
                    logger.info("Popped the Flask app context used for screenshot rendering.")
                except Exception:
                    # Non-fatal: just log and continue
                    logger.exception("Error while popping the Flask app context")

        filename = f"{demo_data['_id']}.png"

        # If caller wants bytes, render into an in-memory buffer
        if return_bytes:
            try:
                # Ask imgkit to return the result as bytes by passing False as output_path
                data = imgkit.from_string(html_content, False, config=config)
                if not data:
                    logger.error("No data produced when rendering screenshot to bytes.")
                    return None
                logger.info(f"Screenshot rendered to bytes for: {demo_data['_id']}")
                return data
            except Exception as e:
                logger.error(f"Failed to render screenshot to bytes: {e}")
                return None

        # Otherwise, write to disk (backwards compatible)
        os.makedirs(output_path, exist_ok=True)
        full_path = os.path.join(output_path, filename)

        if os.path.exists(full_path):
            return f"/static/demo_preview/{filename}"

        try:
            success = imgkit.from_string(html_content, full_path, config=config)
            if not success:
                logger.error("Failed to create screenshot.")
                return None
        except Exception as e:
            logger.error(f"Failed to create screenshot: {e}")
            return None

        logger.info(f"Screenshot created at: {full_path}")
        return full_path.replace("/var/www/mielenosoitukset_fi/mielenosoitukset_fi/", "").replace("../", "/")

    except Exception as e:
        logger.error(f"Failed to create screenshot: {e}")
        return None

import threading

def trigger_screenshot(demo_id, wait=False):
    """
    Trigger the creation of a screenshot for a given demonstration ID and upload to S3.

    Parameters
    ----------
    demo_id : str
        The ID of the demonstration.
    wait : bool
        If True, block until the screenshot is done.

    Returns
    -------
    bool, str
        True/False for success, message.
    """
    def create_screenshot_thread(demo_id):
        from DatabaseManager import DatabaseManager
        from bson import ObjectId
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
                    create_screenshot_thread(demo_id)
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