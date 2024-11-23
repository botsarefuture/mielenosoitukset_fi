import os
import sys

"""
This module initializes the mielenosoitukset_fi package and allows for importing
modules from the package using the mielenosoitukset_fi namespace.

Example:
    import mielenosoitukset_fi.utils.security
"""


# Add the parent directory to the system path to allow for relative imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))