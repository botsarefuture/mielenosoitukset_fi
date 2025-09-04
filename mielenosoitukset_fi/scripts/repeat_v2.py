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

MAX_NEW_DEMOS_PER_RUN = 1000

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


def calculate_next_dates(start_date: datetime, schedule: RepeatSchedule, _created_until: datetime = None):
    """
    Generate next dates, respecting created_until and limiting to MAX_NEW_DEMOS_PER_RUN.
    """
    frequency = schedule.frequency
    interval = schedule.interval or 1
    current_date = datetime.now()
    next_dates = []

    # Normalize end_date
    end_date = schedule.end_date
    if not end_date or end_date == "":
        end_date = current_date + relativedelta(years=1)
    elif isinstance(end_date, str):
        try:
            end_date = datetime.strptime(end_date, "%Y-%m-%d")
        except Exception:
            end_date = current_date + relativedelta(years=1)

    # Adjust start_date if before created_until
    if _created_until and _created_until > start_date:
        start_date = _created_until

    date = start_date
    new_demos_count = 0
    max_iterations = 10000  # hard safety cap
    iterations = 0

    while date <= end_date and new_demos_count < MAX_NEW_DEMOS_PER_RUN and iterations < max_iterations:
        if date >= current_date and (not _created_until or date > _created_until):
            next_dates.append(date)
            new_demos_count += 1

        # Advance
        try:
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
                        date = (date + relativedelta(months=interval)).replace(day=1)
                        w_map = {"monday":0,"tuesday":1,"wednesday":2,"thursday":3,"friday":4,"saturday":5,"sunday":6}
                        n_map = {"first":1,"second":2,"third":3,"fourth":4,"last":-1}
                        wday = w_map[weekday_of_month]
                        n = n_map[nth]
                        if n == -1:
                            date += relativedelta(day=31, weekday=weekday(wday, -1))
                        else:
                            date += relativedelta(weekday=weekday(wday, n))
            elif frequency == "yearly":
                date += relativedelta(years=interval)
            else:
                logger.warning(f"Unknown frequency '{frequency}'")
                break
        except OverflowError:
            logger.warning(f"Date overflow reached: {date}")
            break

        iterations += 1

    logger.debug(f"Next dates: {[d.strftime('%Y-%m-%d') for d in next_dates]}")
    return next_dates

def remove_invalid_child_demonstrations(parent_demo: dict, valid_dates: list[datetime], _created_until: datetime):
    """
    Remove child demos that are not valid, ignoring frozen and already created ones.
    """
    valid_date_strings = {d.strftime("%Y-%m-%d") for d in valid_dates}
    child_demos = demonstrations_collection.find({"parent": parent_demo["_id"]})
    freezed_children = set(parent_demo.get("freezed_children", []))

    for demo in child_demos:
        if demo["_id"] in freezed_children:
            runtime_actions.append({
                "action": "frozen_skip",
                "document": demo,
                "reason": "frozen",
                "timestamp": datetime.now(),
                "executed_by": "system"
            })
            continue

        # Convert demo date string to datetime for comparison
        try:
            demo_date_dt = datetime.strptime(demo["date"], "%Y-%m-%d")
        except Exception:
            logger.warning(f"Invalid date format for child demo {demo['_id']}: {demo['date']}")
            continue

        if demo["date"] not in valid_date_strings and (not _created_until or demo_date_dt > _created_until):
            runtime_actions.append({
                "action": "delete",
                "document": demo,
                "reason": "invalid",
                "timestamp": datetime.now(),
                "executed_by": "system"
            })
            demonstrations_collection.delete_one({"_id": demo["_id"]})
            logger.info(f"Deleted invalid child demo {demo['_id']}")

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
    Process one recurring demonstration: create, update, remove child demos.
    """
    try:
        _demo = RecurringDemonstration.from_dict(demo)
        schedule: RepeatSchedule = _demo.repeat_schedule or RepeatSchedule()
        created_until = _demo.created_until

        demo_date = datetime.strptime(_demo.date, "%Y-%m-%d")
        next_dates = calculate_next_dates(demo_date, schedule, created_until)
        remove_invalid_child_demonstrations(demo, next_dates, created_until)

        bulk_ops = []
        freezed_children = set(demo.get("freezed_children", []))

        for next_date in next_dates:
            if created_until and next_date <= created_until:
                runtime_actions.append({"action":"skip","document":_demo.to_dict(),"reason":"already created","timestamp":datetime.now(),"executed_by":"system"})
                continue

            next_date_str = next_date.strftime("%Y-%m-%d")
            existing_demo = demonstrations_collection.find_one({"date": next_date_str, "parent": demo["_id"]})

            if existing_demo and existing_demo["_id"] in freezed_children:
                runtime_actions.append({"action":"frozen_skip","document":existing_demo,"reason":"frozen","timestamp":datetime.now(),"executed_by":"system"})
                continue

            if existing_demo:
                demonstration = Demonstration.from_dict(existing_demo)
                _data = {"action":"update","document":demonstration.to_dict(),"reason":"update existing","timestamp":datetime.now(),"executed_by":"system"}
                demonstration.update_self_from_recurring(_demo)
                _data["new_document"] = demonstration.to_dict()
                runtime_actions.append(_data)
            else:
                new_demo_data = demo.copy()
                new_demo_data.update({"date": next_date_str,"parent":demo["_id"],"recurring":True})
                new_demo_data.pop("_id", None)
                new_demo = Demonstration.from_dict(new_demo_data)
                bulk_ops.append(UpdateOne({"date": next_date_str,"parent":demo["_id"]},{"$setOnInsert": new_demo.to_dict()}, upsert=True))
                runtime_actions.append({"action":"create","document":new_demo.to_dict(),"reason":"create new","timestamp":datetime.now(),"executed_by":"system"})

        if bulk_ops:
            result = demonstrations_collection.bulk_write(bulk_ops)
            logger.info(f"Processed {result.upserted_count} demos for parent {demo['_id']}")

        # Update created_until
        if next_dates:
            d = RecurringDemonstration.from_dict(demo)
            old_created_until = d.created_until
            d.created_until = next_dates[-1]
            d.save()
            runtime_actions.append({"action":"update","document":d.to_dict(),"old_document":RecurringDemonstration.from_dict(demo).to_dict(),"reason":f"created_until updated from {old_created_until} to {d.created_until}","timestamp":datetime.now(),"executed_by":"system"})

    except Exception as e:
        logger.error(f"Error processing demo {demo.get('_id')}: {e}")
        logger.error(format_exc())


def handle_repeating_demonstrations():
    demos = recu_demos_collection.find()
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(process_demo, demo) for demo in demos]
        for future in as_completed(futures):
            future.result()

def find_duplicates() -> list[dict]:
    demos = list(demonstrations_collection.find({"hide":False,"in_past":False,"recurring":True}))
    duplicates = []

    def demo_match(d1,d2):
        return d1["title"]==d2["title"] and d1["date"]==d2["date"] and d1["city"]==d2["city"] and d1["address"]==d2["address"] and (d1.get("event_type")==d2.get("event_type") or d1.get("type")==d2.get("type"))

    for i,demo in enumerate(demos):
        group = {"ids":[demo["_id"]]}
        for other_demo in demos[i+1:]:
            if demo_match(demo, other_demo):
                group["ids"].append(other_demo["_id"])
        if len(group["ids"])>1:
            duplicates.append(group)
    return duplicates


def merge_duplicates() -> int:
    duplicates = find_duplicates()
    merged_count = 0
    for group in duplicates:
        ids = group["ids"]
        base_demo = Demonstration.from_dict(demonstrations_collection.find_one({"_id": ids[0]}))
        for dup_id in ids[1:]:
            try:
                base_demo.merge(dup_id)
                runtime_actions.append({"action":"merge","document":base_demo.to_dict(),"reason":"merge duplicate","timestamp":datetime.now(),"executed_by":"system"})
                merged_count += 1
            except Exception as e:
                logger.error(f"Error merging {dup_id}: {e}")
    logger.info(f"Merged {merged_count} duplicate demos")
    return merged_count


def process_runtime_actions():
    if runtime_actions:
        for action in runtime_actions:
            action["runtime_id"] = RUNTIME_ID
        runtime_log_collection.insert_many(runtime_actions)
    runtimes_collection.update_one({"_id": RUNTIME_ID},{"$set":{"end_time":datetime.now(),"status":"completed"}})



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
