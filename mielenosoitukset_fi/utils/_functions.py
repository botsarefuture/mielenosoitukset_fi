"""
_functions.py

This module provides utility functions for the application.

Functions
---------
get_cur_dir() -> str
    Returns the current directory of the file where this function is called.

load_version() -> str
    Loads the current version of the application from the VERSION file.
"""

import os


def get_cur_dir() -> str:
    """Returns the current directory of the file where this function is called.

    This function determines the full path of the file using `__file__`,
    then extracts and returns the directory part of the path.

    Returns
    -------
    str
        The current directory of the file.
    """
    _FULL_PATH = os.path.realpath(__file__)
    _CUR_DIR = os.path.dirname(_FULL_PATH)
    return _CUR_DIR


_CUR_DIR = get_cur_dir()  # Get the current directory of the file


def load_version() -> str:
    """Load the current version of the application from the VERSION file.

    Returns
    -------
    str
        The version string currently running.

    Changelog
    ---------
    v2.4.0:
        - Added this function to load the version.
    """
    with open(os.path.join(_CUR_DIR, "data", "VERSION")) as f:
        version = f.read().strip()

    if not version.lower().startswith("v"):
        return f"v{version}"

    return version
