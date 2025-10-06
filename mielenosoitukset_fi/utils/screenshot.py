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
        if not has_app_context():
            raise ValueError("No Flask application context found.")

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
    Trigger the creation of a screenshot for a given demonstration ID.

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

        _path = os.path.join(_CUR_DIR, "static/demo_preview", f"{demo_id}.png")
        if os.path.exists(_path):
            logger.info(f"Screenshot already exists: {demo_id}")
            return  # Already exists

        try:
            db_man = DatabaseManager.get_instance()
            mongo = db_man.get_db()
            data = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
            if not data:
                logger.error(f"No demonstration found with ID {demo_id}")
                return

            from mielenosoitukset_fi.utils.classes.Demonstration import Demonstration
        
            demo = Demonstration.from_dict(data)

            with current_app.app_context():
                path = create_screenshot(demo)
                if path:
                    logger.info(f"Screenshot created: {path}")
                else:
                    logger.error(f"Failed to create screenshot for demo {demo_id}")
        except Exception as e:
            logger.error(f"Exception in screenshot thread: {e}")

    try:
        thread = threading.Thread(target=create_screenshot_thread, args=(demo_id,))
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