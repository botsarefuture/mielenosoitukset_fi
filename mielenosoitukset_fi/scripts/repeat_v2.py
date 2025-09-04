"""
Recurring Demonstrations Processor
==================================

This module handles recurring demonstrations in the database. It calculates
future occurrences, removes invalid child demonstrations, and merges duplicates.

Modules
-------
os : module
    Provides a way of using operating system dependent functionality.
logging : module
    Provides logging capabilities.
concurrent.futures : module
    Enables parallel execution using threads.
pymongo : module
    For MongoDB interactions.
datetime : module
    Date and time manipulation.
dateutil.relativedelta : module
    Relative date calculations for recurring events.
config : module
    Project configuration module.
mielenosoitukset_fi.utils.classes : module
    Demonstration and RecurringDemonstration classes.
traceback : module
    Format exception tracebacks for logging.

Version
-------
v4.3.3

Modification Notes
------------------
- v4.3.3: Ensured repeat_schedule is preserved when processing demonstrations.
- Added Numpydoc-style docstrings consistently across functions.
- Improved logging for debugging recurring demonstrations.
"""

import copy
import os
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pymongo import MongoClient, UpdateOne
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta, weekday
from config import Config
from mielenosoitukset_fi.utils.classes import Demonstration, RecurringDemonstration
from traceback import format_exc
from mielenosoitukset_fi.utils import VERSION
from mielenosoitukset_fi.utils.classes.RepeatSchedule import RepeatSchedule

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Database setup
client = MongoClient(os.getenv("MONGO_URI", Config.MONGO_URI))
db = client["mielenosoitukset"]
recu_demos_collection = db["recu_demos"]
demonstrations_collection = db["demonstrations"]
runtime_log_collection = db["runtime_log"]
runtimes_collection = db["runtimes"]
runtime_actions = []


def _get_runtime_id():
    """
    Create a runtime entry in the database.

    Returns
    -------
    ObjectId
        The ID of the newly created runtime entry.
    """
    runtime_entry = {
        "start_time": datetime.now(),
        "end_time": None,
        "status": "running",
        "script_id": "repeat_v2.py",
        "version": VERSION
    }
    result = runtimes_collection.insert_one(runtime_entry)
    return result.inserted_id


RUNTIME_ID = _get_runtime_id()


def calculate_next_dates(start_date: datetime, schedule: RepeatSchedule):
    """
    Calculate the next occurrences for a recurring demonstration.

    Parameters
    ----------
    start_date : datetime
        The starting date of the recurring demonstration.
    schedule : RepeatSchedule
        Object containing frequency, interval, end_date, and optional
        monthly or yearly options.

    Returns
    -------
    list of datetime
        A list of datetime objects representing the future demonstration dates.
    """
    frequency = schedule.frequency
    interval = schedule.interval
    current_date = datetime.now()
    next_dates = []

    logger.debug(f"Calculating next dates: frequency={frequency}, interval={interval}")

    end_date = schedule.end_date or (current_date + relativedelta(years=1))
    date = start_date

    while date <= end_date:
        if date >= current_date:
            next_dates.append(date)

        if frequency == "daily":
            date += timedelta(days=interval)
        elif frequency == "weekly":
            date += timedelta(weeks=interval)
        elif frequency == "monthly":
            if schedule.monthly_option == "day_of_month":
                date += relativedelta(months=interval)
            elif schedule.monthly_option == "nth_weekday":
                nth = schedule.nth_weekday
                weekday_of_month = schedule.weekday_of_month
                if nth and weekday_of_month:
                    # move to next month first
                    date = (date + relativedelta(months=interval)).replace(day=1)
                    weekday_map = {
                        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                        "friday": 4, "saturday": 5, "sunday": 6
                    }
                    nth_map = {"first": 1, "second": 2, "third": 3, "fourth": 4, "last": -1}
                    wday = weekday_map[weekday_of_month]
                    n = nth_map[nth]
                    if n == -1:
                        date += relativedelta(day=31, weekday=weekday(wday, -1))
                    else:
                        date += relativedelta(weekday=weekday(wday, n))
        elif frequency == "yearly":
            date += relativedelta(years=interval)
        else:
            logger.warning(f"Unknown frequency '{frequency}' for RecurringDemonstration")
            break

    logger.debug(f"Next dates calculated: {[d.strftime('%Y-%m-%d') for d in next_dates]}")
    return next_dates


def remove_invalid_child_demonstrations(parent_demo: dict, valid_dates: list[datetime]):
    """
    Remove child demonstrations that are no longer valid, unless they are frozen.

    Parameters
    ----------
    parent_demo : dict
        The parent demonstration document from the database.
    valid_dates : list of datetime
        List of valid future dates for child demonstrations.

    Returns
    -------
    None
    """
    valid_date_strings = {d.strftime("%Y-%m-%d") for d in valid_dates}
    child_demos = demonstrations_collection.find({"parent": parent_demo["_id"]})
    freezed_children = set(parent_demo.get("freezed_children", []))

    for demo in child_demos:
        if demo["_id"] in freezed_children:
            runtime_actions.append(
                {
                    "action": "frozen_skip",
                    "document": demo,
                    "reason": "Child demo is frozen",
                    "timestamp": datetime.now(),
                    "executed_by": "system"
                }
            )
            logger.debug(f"Skipped frozen child demo {demo['_id']}")
            continue

        if demo["date"] not in valid_date_strings and not demo.get("in_past", False) and not demo.get("locked", False):
            runtime_actions.append(
                {
                    "action": "delete",
                    "document": demo,
                    "reason": "Date not in valid dates",
                    "timestamp": datetime.now(),
                    "executed_by": "system"
                }
            )
            demonstrations_collection.delete_one({"_id": demo["_id"]})
            logger.info(f"Deleted invalid child demonstration {demo['_id']}")


def get(obj: dict, key: str, default=None):
    """
    Safe dictionary access with default fallback.

    Parameters
    ----------
    obj : dict
        The dictionary object.
    key : str
        The key to retrieve.
    default : optional
        Value to return if the key is missing or None.

    Returns
    -------
    object
        Value of the key or default.
    """
    result = obj.get(key, default)
    return default if result is None else result



def process_demo(demo: dict):
    """
    Process a single recurring demonstration: calculate future dates,
    remove invalid children, and insert/update child demonstrations.

    Ensures that `repeat_schedule` is not removed and frozen children are not modified.

    Parameters
    ----------
    demo : dict
        Parent demonstration document.

    Returns
    -------
    None

    Raises
    ------
    RuntimeWarning
        If processing of the demonstration fails.
    """
    try:
        _demo = RecurringDemonstration.from_dict(demo)
        _demo_dict = _demo.to_dict()

        logger.debug(f"Processing RecurringDemonstration {demo['_id']}")

        demo_date = datetime.strptime(_demo.date, "%Y-%m-%d")
        schedule: RepeatSchedule = _demo.repeat_schedule or RepeatSchedule(frequency="daily", interval=1)
        created_until = _demo.created_until
        freezed_children = set(demo.get("freezed_children", []))

        next_dates = calculate_next_dates(demo_date, schedule)
        remove_invalid_child_demonstrations(demo, next_dates)

        bulk_operations = []
        for next_date in next_dates:
            if next_date <= created_until:
                runtime_actions.append(
                    {
                        "action": "skip",
                        "document": _demo_dict,
                        "reason": "The date is already created",
                        "timestamp": datetime.now(),
                        "executed_by": "system"
                    }
                )
                continue

            next_date_str = next_date.strftime("%Y-%m-%d")
            existing_demo = demonstrations_collection.find_one({"date": next_date_str, "parent": demo["_id"]})

            # Skip frozen children
            if existing_demo and existing_demo["_id"] in freezed_children:
                runtime_actions.append(
                    {
                        "action": "frozen_skip",
                        "document": existing_demo,
                        "reason": "Child demo is frozen",
                        "timestamp": datetime.now(),
                        "executed_by": "system"
                    }
                )
                logger.debug(f"Skipped frozen child demo {existing_demo['_id']}")
                continue

            if existing_demo:
                demonstration = Demonstration.from_dict(existing_demo)
                _data = {
                    "action": "update",
                    "document": demonstration.to_dict(),
                    "reason": "Updating existing demonstration",
                    "timestamp": datetime.now(),
                    "executed_by": "system"
                }
                demonstration.update_self_from_recurring(_demo)
                _data["new_document"] = demonstration.to_dict()
                runtime_actions.append(_data)

            else:
                new_demo_data = demo.copy()
                new_demo_data.update(
                    {"date": next_date_str, "parent": demo["_id"], "recurring": True}
                )
                new_demo_data.pop("_id", None)  # keep repeat_schedule intact
                new_demo = Demonstration.from_dict(new_demo_data)
                bulk_operations.append(
                    UpdateOne(
                        {"date": next_date_str, "parent": demo["_id"]},
                        {"$setOnInsert": new_demo.to_dict()},
                        upsert=True
                    )
                )
                runtime_actions.append(
                    {
                        "action": "create",
                        "document": new_demo.to_dict(),
                        "reason": "Creating new demonstration",
                        "timestamp": datetime.now(),
                        "executed_by": "system"
                    }
                )

        if bulk_operations:
            result = demonstrations_collection.bulk_write(bulk_operations)
            logger.info(f"Processed {result.upserted_count} demonstrations for parent {demo['_id']}")

        d = RecurringDemonstration.from_dict(demo)
        _old_d = copy.deepcopy(d)
        d.created_until = next_dates[-1] if next_dates else None # if next_dates is empty, dont do this
        d.save()

        runtime_actions.append({
            "action": "update",
            "document": d.to_dict(),
            "reason": f"Updated created_until from {_old_d.created_until} to {d.created_until}",
            "timestamp": datetime.now(),
            "executed_by": "system",
            "old_document": _old_d.to_dict()
        })

    except Exception as e:
        logger.error(f"Error processing demonstration {demo.get('_id')}: {e}")
        logger.error(format_exc())
        raise RuntimeWarning from e


def handle_repeating_demonstrations():
    """
    Process all repeating demonstrations concurrently.

    Returns
    -------
    None
    """
    try:
        demos = recu_demos_collection.find()
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(process_demo, demo) for demo in demos]
            for future in as_completed(futures):
                future.result()
    except Exception as e:
        logger.error(f"Error handling repeating demonstrations: {e}")


def find_duplicates() -> list[dict]:
    """
    Identify duplicate recurring demonstrations.

    Returns
    -------
    list of dict
        Each dict contains a list of duplicate demonstration IDs under 'ids'.
    """
    def demo_match(demo1, demo2):
        return (
            demo1["title"] == demo2["title"] and
            demo1["date"] == demo2["date"] and
            demo1["city"] == demo2["city"] and
            demo1["address"] == demo2["address"] and
            (demo1.get("event_type") == demo2.get("event_type") or demo1.get("type") == demo2.get("type"))
        )

    demos = list(demonstrations_collection.find({"hide": False, "in_past": False, "recurring": True}))
    duplicates = []

    for i, demo in enumerate(demos):
        duplicate_group = {"ids": [demo["_id"]]}
        for other_demo in demos[i + 1:]:
            if demo_match(demo, other_demo):
                duplicate_group["ids"].append(other_demo["_id"])
        if len(duplicate_group["ids"]) > 1:
            duplicates.append(duplicate_group)

    return duplicates


def merge_duplicates() -> int:
    """
    Merge duplicate recurring demonstrations.

    Returns
    -------
    int
        The number of merged duplicates.
    """
    duplicates = find_duplicates()
    merged_count = 0

    for group in duplicates:
        ids = group["ids"]
        base_demo = demonstrations_collection.find_one({"_id": ids[0]})
        base_demo = Demonstration.from_dict(base_demo)
        for duplicate_id in ids[1:]:
            try:
                base_demo.merge(duplicate_id)
                runtime_actions.append(
                    {
                        "action": "merge",
                        "document": base_demo.to_dict(),
                        "reason": "Merging duplicate demonstration",
                        "timestamp": datetime.now(),
                        "executed_by": "system"
                    }
                )
                merged_count += 1
            except Exception as e:
                logger.error(f"Error merging duplicate {duplicate_id}: {e}")

    logger.info(f"Merged {merged_count} duplicate demonstrations.")
    return merged_count


def process_runtime_actions():
    """
    Save runtime actions and update the runtime status in the database.

    Returns
    -------
    None
    """
    rac = []
    for action in runtime_actions:
        action["runtime_id"] = RUNTIME_ID
        rac.append(action)

    runtime_log_collection.insert_many(rac)
    runtimes_collection.update_one(
        {"_id": RUNTIME_ID},
        {"$set": {"end_time": datetime.now(), "status": "completed"}}
    )


def main():
    """
    Entry point for processing recurring demonstrations.

    Returns
    -------
    None
    """
    logger.info("Starting demonstration processing.")
    handle_repeating_demonstrations()
    total_merged = merge_duplicates()
    logger.info(f"Total duplicates merged: {total_merged}")
    process_runtime_actions()


if __name__ == "__main__":
    main()
