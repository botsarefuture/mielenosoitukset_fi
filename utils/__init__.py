"""
This module initializes the utility functions for the mielenosoitukset_fi package.

It imports the `load_version` and `get_cur_dir` functions from the `_functions` module
and uses them to set the `VERSION` and `_CUR_DIR` variables.

Attributes
----------
VERSION : str
    The current version of the package.
_CUR_DIR : str
    The current directory of the package.
"""

from ._functions import load_version, get_cur_dir

VERSION = load_version()
_CUR_DIR = get_cur_dir()

