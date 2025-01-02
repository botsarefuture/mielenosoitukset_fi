from flask import render_template, url_for
import imgkit
import os
import tempfile

from mielenosoitukset_fi.utils.logger import logger
from mielenosoitukset_fi.utils import _CUR_DIR
from mielenosoitukset_fi.utils.classes.Demonstration import Demonstration

# Set XDG_CACHE_HOME to a writable directory
os.environ["XDG_CACHE_HOME"] = tempfile.mkdtemp()
# Set XDG_RUNTIME_DIR to a writable directory
os.environ["XDG_RUNTIME_DIR"] = tempfile.mkdtemp()
config = imgkit.config()

def create_screenshot(demo_data, output_path="/var/www/mielenosoitukset_fi/mielenosoitukset_fi/static/demo_preview"):
    """
    Create a PNG screenshot from the preview template.

    Parameters
    ----------
    demo_data : dict
        Dictionary containing the demonstration data.
    output_path : str, optional
        Directory path where the screenshot PNG will be saved.

    Returns
    -------
    str or None
        Full path of the created PNG file, or None if creation failed.
    """
    try:
        os.makedirs(output_path, exist_ok=True)
        
        if not isinstance(demo_data, dict):
            if hasattr(demo_data, "to_dict"):
                demo_data = demo_data.to_dict(True)
            else:
                raise ValueError("Invalid demonstration data provided.")
        
        html_content = render_template("preview.html", demo=demo_data)
        filename = f"{demo_data['_id']}.png"
        if os.path.exists(os.path.join(output_path, filename)):
            return f"/static/demo_preview/{filename}"
        
        full_path = os.path.join(output_path, filename)
        
        _return_path = full_path.replace("/var/www/mielenosoitukset_fi/mielenosoitukset_fi/", "").replace("../", "/")
        
        try:
            success = imgkit.from_string(html_content, full_path, config=config)
            if not success:
                logger.error("Failed to create screenshot.")
                return None
            
        except Exception as e:
            logger.error(f"Failed to create screenshot: {e}")
            return None

        if success:
            logger.info(f"Screenshot created at: {full_path}")
        return _return_path
        
    except Exception as e:
        logger.error(f"Failed to create screenshot: {e}")
        return None
    
def trigger_screenshot(demo_id):
    """
    Trigger the creation of a screenshot for a given demonstration ID.

    Parameters
    ----------
    demo_id : str
        The ID of the demonstration.

    Returns
    -------
    Response
        Redirects to the screenshot URL if successful, otherwise to an error image.
    """
    _path = os.path.join(_CUR_DIR, "static/demo_preview", f"{demo_id}.png")
    if os.path.exists(_path):
        return f"/static/demo_preview/{demo_id}.png"
    
    from DatabaseManager import DatabaseManager
    db_man = DatabaseManager.get_instance()
    mongo = db_man.get_db()
    from bson import ObjectId
    
    data = mongo.demonstrations.find_one({"_id": ObjectId(demo_id)})
    demo = Demonstration.from_dict(data)
    screenshot_path = create_screenshot(demo)
    if screenshot_path is None:
        return url_for("static", filename="img/e.png")
    return url_for("static", filename=screenshot_path.replace("static/", "").replace("//", "/"))
    
if __name__ == "__main__":
    demo_data = {
        "_id": "demo_id",
        "title": "Demo Title",
        "date": "2022-12-31",
        "location": "Demo Location",
        "description": "This is a demonstration description.",
    }
    try:
        screenshot_path = create_screenshot(demo_data)
        print(f"Screenshot saved at: {screenshot_path}")
    except Exception as e:
        print(f"Error: {e}")
