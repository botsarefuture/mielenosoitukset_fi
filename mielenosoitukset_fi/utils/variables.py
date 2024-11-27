"""
Module for loading and managing configuration data from JSON files.

This module provides functions to load JSON data from files located in the "data" directory.
It also defines constants that store the loaded data for use throughout the application.

Functions
---------
load_from_file(_filename)
    Load and parse JSON data from a specified file located in the "data" directory.

Constants
---------
CITY_LIST : dict
    A dictionary containing the parsed JSON data from 'city_list.json'.
PERMISSIONS_GROUPS : dict
    A dictionary containing the parsed JSON data from 'permission_groups.json'.
EVENT_TYPES : dict
    A dictionary containing the parsed JSON data from 'event_types.json'.

Changelog
---------
v2.4.0:
    - Added this module to load JSON data from the ".utils" directory.
v2.5.0:
    - Moved this module to utils.variables, and moved files to ./data directory.
"""

import json
import os

from mielenosoitukset_fi.utils.database import DEMO_FILTER
from . import _CUR_DIR


def load_from_file(_filename):
    """
    Load and parse JSON data from a specified file located in the "data" directory.

    This function reads the content of a JSON file and returns it as a Python dictionary.
    The file is expected to be located in the `/data/` folder relative to the current working directory.

    Parameters
    ----------
    _filename : str
        The name of the JSON file to load (e.g., 'city_list.json').

    Returns
    -------
    dict
        A dictionary containing the parsed JSON data.

    Raises
    ------
    FileNotFoundError
        If the specified file does not exist in the "/data/" directory.
    json.JSONDecodeError
        If the file is not a valid JSON file.

    Changelog
    ---------
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
EVENT_TYPES = load_from_file("event_types.json")
