from flask import render_template
import imgkit
import os
import tempfile

from mielenosoitukset_fi.utils.logger import logger

# Set XDG_CACHE_HOME to a writable directory
os.environ["XDG_CACHE_HOME"] = tempfile.mkdtemp()
config = imgkit.config()

def create_screenshot(demo_data, output_path="../static/demo_preview/"):
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
    str
        Full path of the created PNG file.
    """
    try:
        base_path = os.path.abspath(os.path.dirname(__file__))
        output_path = os.path.join(base_path, output_path)
        os.makedirs(output_path, exist_ok=True)
        
        demo_data = demo_data.to_dict(True)
        html_content = render_template("preview.html", demo=demo_data)
        filename = f"{demo_data['_id']}.png"
        full_path = os.path.join(output_path, filename)
        
        _return_path = full_path.replace(base_path, "").replace("../", "/")

        imgkit.from_string(html_content, full_path, config=config)
        logger.info(f"Screenshot created at: {full_path}")
        return _return_path
    except Exception as e:
        logger.error(f"Failed to create screenshot: {e}")
        raise

if __name__ == "__main__":
    demo_data = {
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