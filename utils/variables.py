import json
import os

from . import _CUR_DIR

def load_from_file(_filename):
    """
    Load and parse JSON data from a specified file located in the ".utils" directory.

    This function reads the content of a JSON file and returns it as a Python dictionary.
    The file is expected to be located in the `/utils/data/` folder relative to the current working directory.

    Args:
        _filename (str): The name of the JSON file to load (e.g., 'city_list.json').

    Returns:
        dict: A dictionary containing the parsed JSON data.

    Raises:
        FileNotFoundError: If the specified file does not exist in the "/utils/data/" directory.
        json.JSONDecodeError: If the file is not a valid JSON file.

    Changelog:
    ----------
    v2.4.0:
        - Added this function to load JSON data from the ".utils" directory.

    v2.5.0:
        - Moved this function to utils.variables, and moved files to ./data directory.
    """
    file_path = os.path.join(_CUR_DIR, "data", _filename)

    # Attempt to open and load the file
    with open(file_path, encoding="utf-8") as f:
        return json.load(f)


CITY_LIST = load_from_file("city_list.json")
PERMISSIONS_GROUPS = load_from_file("permission_groups.json")
