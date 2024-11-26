import os
import glob

# Dynamically import all classes in the current directory
modules = glob.glob(os.path.join(os.path.dirname(__file__), "*.py"))
for module in modules:
    if os.path.basename(module) == "__init__.py":
        continue
    module_name = os.path.basename(module)[:-3]
    class_name = "".join([part for part in module_name.split("_")])
    exec(f"from .{module_name} import {class_name}")

from utils.database import get_database_manager

DB = get_database_manager()
