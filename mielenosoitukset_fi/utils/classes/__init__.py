import os
import glob

from mielenosoitukset_fi.utils.classes.AdminActivity import AdminActivity, UserDataFormatter
from mielenosoitukset_fi.utils.classes.BaseModel import BaseModel
from mielenosoitukset_fi.utils.classes.Demonstration import Demonstration
from mielenosoitukset_fi.utils.classes.MemberShip import MemberShip
from mielenosoitukset_fi.utils.classes.Organization import Organization
from mielenosoitukset_fi.utils.classes.Organizer import Organizer
from mielenosoitukset_fi.utils.classes.RecurringDemonstration import RecurringDemonstration
from mielenosoitukset_fi.utils.classes.RepeatSchedule import RepeatSchedule

__all__ = [
    "AdminActivity",
    "UserDataFormatter",
    "BaseModel",
    "Demonstration",
    "MemberShip",
    "Organization",
    "Organizer",
    "RecurringDemonstration",
    "RepeatSchedule"
]

# Dynamically import all classes in the current directory
modules = glob.glob(os.path.join(os.path.dirname(__file__), "*.py"))
for module in modules:
    if os.path.basename(module) == "__init__.py":
        continue
    module_name = os.path.basename(module)[:-3]
    class_name = "".join([part for part in module_name.split("_")])
    exec(f"from .{module_name} import {class_name}")

from mielenosoitukset_fi.utils.database import get_database_manager

DB = get_database_manager()
