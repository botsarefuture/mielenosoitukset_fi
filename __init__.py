import os
import sys

"""
This module initializes the mielenosoitukset_fi package and allows for importing
modules from the package using the mielenosoitukset_fi namespace.

Example:
    import mielenosoitukset_fi.utils.security
"""


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
INNER_PACKAGE_DIR = os.path.join(ROOT_DIR, "mielenosoitukset_fi")

# Add the repository root to the system path to allow for relative imports.
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

# Expose the nested application package as part of this package namespace so
# importers consistently resolve `mielenosoitukset_fi.*` under both unittest
# and pytest collection modes.
if os.path.isdir(INNER_PACKAGE_DIR) and INNER_PACKAGE_DIR not in __path__:
    __path__.append(INNER_PACKAGE_DIR)
