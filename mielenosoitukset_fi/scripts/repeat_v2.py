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
from datetime import datetime, date, timedelta
import argparse
from typing import Union, Optional
from dateutil.relativedelta import relativedelta, weekday
from config import Config
from mielenosoitukset_fi.utils.classes import Demonstration, RecurringDemonstration
from traceback import format_exc
from mielenosoitukset_fi.utils import VERSION
from mielenosoitukset_fi.utils.classes.RepeatSchedule import RepeatSchedule

# Dry-run flag (can be overridden from CLI)
DRY_RUN = False
# Force recheck flag: when True, verify existing child demos match schedule
FORCE_RECHECK = False
# If True and FORCE_RECHECK, attempt to fix mismatches (mutating DB unless DRY_RUN)
RECHECK_FIX = False

# Helper: map weekday names to index and a weekly alignment helper
WEEKDAY_MAP = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

def next_weekday(dt: date, target_weekday: str, interval: int = 1) -> date:
    """
    Advance `dt` to the next `target_weekday`, respecting weekly `interval`.

    Parameters
    ----------
    dt : date
        Starting date
    target_weekday : str
        Weekday name (e.g., 'friday')
    interval : int
        Number of weeks between repeats (1 means every week)

    Returns
    -------
    date
        Next date that falls on the target weekday according to interval
    """
    target_wd = WEEKDAY_MAP[target_weekday.lower()]
    current_wd = dt.weekday()

    days_until = (target_wd - current_wd) % 7
    if days_until == 0:
        days_until = 7 * interval
    else:
        days_until += 7 * (interval - 1)

    return dt + timedelta(days=days_until)

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
stats_collection = db["recu_stats"]



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
        "version": VERSION,
    }
    if DRY_RUN:
        logger.info(f"DRY RUN: would insert runtime entry: {runtime_entry}")
        return None
    result = runtimes_collection.insert_one(runtime_entry)
    return result.inserted_id


RUNTIME_ID = _get_runtime_id()


def calculate_next_dates(start_date: Union[datetime, date], schedule: RepeatSchedule, _created_until: Optional[Union[datetime, date]] = None):
    """
    Generate next dates, respecting created_until and limiting to MAX_NEW_DEMOS_PER_RUN.

    Notes
    -----
    This function operates on date-only values (datetime.date) to avoid
    time-of-day and timezone related off-by-one issues where a date at
    midnight could be considered "previous day" depending on server time.
    """
    frequency = schedule.frequency
    interval = schedule.interval or 1
    # Use date-only comparisons to avoid time-of-day issues
    current_date = datetime.now().date()
    next_dates = []

    # Normalize end_date
    end_date = schedule.end_date
    if not end_date or end_date == "":
        end_date = (datetime.now() + relativedelta(years=1)).date()
    elif isinstance(end_date, str):
        try:
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        except Exception:
            end_date = (datetime.now() + relativedelta(years=1)).date()

    # Convert start_date and created_until to date objects if needed
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    if isinstance(_created_until, datetime):
        _created_until = _created_until.date()

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
                date = date + timedelta(days=interval)
            elif frequency == "weekly":
                # If a weekday is specified in the schedule, align using next_weekday
                if getattr(schedule, "weekday", None):
                    try:
                        date = next_weekday(date, str(schedule.weekday), interval=schedule.interval or 1)
                    except Exception:
                        # Fallback to simple week increment
                        date = date + timedelta(weeks=interval)
                else:
                    date = date + timedelta(weeks=interval)
            elif frequency == "monthly":
                if schedule.monthly_option == "day_of_month":
                    date = date + relativedelta(months=interval)
                elif schedule.monthly_option == "nth_weekday":
                    nth = schedule.nth_weekday
                    weekday_of_month = schedule.weekday_of_month
                    if nth and weekday_of_month:
                        # move to first day of the target month
                        date = (date + relativedelta(months=interval)).replace(day=1)
                        w_map = {"monday":0,"tuesday":1,"wednesday":2,"thursday":3,"friday":4,"saturday":5,"sunday":6}
                        n_map = {"first":1,"second":2,"third":3,"fourth":4,"last":-1}
                        wday = w_map[weekday_of_month]
                        n = n_map[nth]
                        if n == -1:
                            date = date + relativedelta(day=31, weekday=weekday(wday, -1))
                        else:
                            date = date + relativedelta(weekday=weekday(wday, n))
            elif frequency == "yearly":
                date = date + relativedelta(years=interval)
            else:
                logger.warning(f"Unknown frequency '{frequency}'")
                break
        except OverflowError:
            logger.warning(f"Date overflow reached: {date}")
            break

        iterations += 1

    logger.debug(f"Next dates: {[d.strftime('%Y-%m-%d') for d in next_dates]}")
    return next_dates

def update_parent_stats(parent_id):
    """
    Compute total, future, and past demonstration counts for a recurring parent.
    Saves results into `recu_stats`.
    """
    now = datetime.now().date()
    # Only include visible demos
    siblings = list(demonstrations_collection.find({"parent": parent_id, "hide": False}))
    
    total_count = len(siblings)
    future_count = sum(1 for d in siblings if datetime.strptime(d["date"], "%Y-%m-%d").date() > now)
    past_count = sum(1 for d in siblings if datetime.strptime(d["date"], "%Y-%m-%d").date() < now)

    stats_doc = {
        "parent": parent_id,
        "total_count": total_count,
        "future_count": future_count,
        "past_count": past_count,
        "last_updated": datetime.now()
    }

    if DRY_RUN:
        logger.info(f"DRY RUN: would upsert stats for parent {parent_id}: {stats_doc}")
    else:
        stats_collection.update_one({"parent": parent_id}, {"$set": stats_doc}, upsert=True)
        logger.info(f"Updated stats for parent {parent_id}")


def remove_invalid_child_demonstrations(parent_demo: dict, valid_dates: list[date], _created_until: Union[datetime, date]):
    """
    Remove child demos that are not valid, ignoring frozen and already created ones.
    """
    # Ensure valid_dates are date objects (they may have been produced by calculate_next_dates)
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

        # Convert demo date string to date for comparison
        try:
            demo_date_dt = datetime.strptime(demo["date"], "%Y-%m-%d").date()
        except Exception:
            logger.warning(f"Invalid date format for child demo {demo['_id']}: {demo['date']}")
            continue

        # Normalize _created_until to date if datetime passed
        created_until_date = _created_until.date() if isinstance(_created_until, datetime) else _created_until

        if demo["date"] not in valid_date_strings and (not created_until_date or demo_date_dt > created_until_date):
            runtime_actions.append({
                "action": "delete",
                "document": demo,
                "reason": "invalid",
                "timestamp": datetime.now(),
                "executed_by": "system"
            })
            if DRY_RUN:
                logger.info(f"DRY RUN: would delete invalid child demo {demo['_id']}")
            else:
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



def process_demo(demo: dict, only_calculate: bool = False):
    """
    Process one recurring demonstration: create, update, remove child demos.
    """
    try:
        _demo = RecurringDemonstration.from_dict(demo)
        schedule: RepeatSchedule = _demo.repeat_schedule or RepeatSchedule()
        created_until = _demo.created_until

        # Normalize demo_date and created_until to date objects for consistent comparisons
        demo_date = datetime.strptime(_demo.date, "%Y-%m-%d").date()
        created_until_date = created_until.date() if isinstance(created_until, datetime) else created_until
        next_dates = calculate_next_dates(demo_date, schedule, created_until_date)
        
        # Only calculate stats if requested
        if only_calculate:
            remove_invalid_child_demonstrations(demo, next_dates, created_until_date)
            update_parent_stats(demo["_id"])
            return
        
        # If FORCE_RECHECK, inspect existing child demos and ensure they match schedule
        if FORCE_RECHECK:
            child_demos = list(demonstrations_collection.find({"parent": demo["_id"]}))
            for child in child_demos:
                if child["_id"] in set(demo.get("freezed_children", [])):
                    continue
                try:
                    child_date = datetime.strptime(child["date"], "%Y-%m-%d").date()
                except Exception:
                    logger.warning(f"Invalid date format for child demo {child['_id']}: {child.get('date')}")
                    continue

                # Weekly schedule: check weekday
                if schedule and schedule.frequency == "weekly" and getattr(schedule, "weekday", None):
                    desired_wd = WEEKDAY_MAP.get(str(schedule.weekday).lower())
                    if desired_wd is not None and child_date.weekday() != desired_wd:
                        msg = f"Mismatch for child {child['_id']}: has weekday {child_date.weekday()} but expected {desired_wd} for parent {demo['_id']}"
                        if RECHECK_FIX:
                            # Find nearest date within the same week (offset -3..3)
                            corrected = None
                            for off in range(-3, 4):
                                cand = child_date + timedelta(days=off)
                                if cand.weekday() == desired_wd:
                                    corrected = cand
                                    break
                            if corrected:
                                if DRY_RUN:
                                    logger.info(f"DRY RUN: would update child {child['_id']} date from {child_date} to {corrected} ({msg})")
                                    runtime_actions.append({"action":"fix","document":child,"reason":f"would change date to {corrected}","timestamp":datetime.now(),"executed_by":"system"})
                                else:
                                    demonstrations_collection.update_one({"_id": child["_id"]}, {"$set": {"date": corrected.strftime("%Y-%m-%d")}})
                                    runtime_actions.append({"action":"fix","document":child,"reason":f"changed date to {corrected}","timestamp":datetime.now(),"executed_by":"system"})
                                    logger.info(f"Updated child {child['_id']} date from {child_date} to {corrected}")
                            else:
                                logger.warning(msg + " and could not find nearby matching weekday")
                        else:
                            logger.info(msg)

                # Monthly option: day_of_month check
                if schedule and schedule.frequency == "monthly" and getattr(schedule, "monthly_option", None) == "day_of_month" and getattr(schedule, "day_of_month", None):
                    if schedule.day_of_month is None:
                        desired_dom = None
                    else:
                        desired_dom = int(schedule.day_of_month)
                    if desired_dom is None:
                        # Nothing to check
                        pass
                    if child_date.day != desired_dom:
                        msg = f"Mismatch for child {child['_id']}: has day {child_date.day} but expected day {desired_dom} for parent {demo['_id']}"
                        if RECHECK_FIX:
                            try:
                                if desired_dom is None:
                                    raise ValueError("No desired day specified")
                                corrected = child_date.replace(day=desired_dom)
                                if DRY_RUN:
                                    logger.info(f"DRY RUN: would update child {child['_id']} date from {child_date} to {corrected} ({msg})")
                                    runtime_actions.append({"action":"fix","document":child,"reason":f"would change date to {corrected}","timestamp":datetime.now(),"executed_by":"system"})
                                else:
                                    demonstrations_collection.update_one({"_id": child["_id"]}, {"$set": {"date": corrected.strftime("%Y-%m-%d")}})
                                    runtime_actions.append({"action":"fix","document":child,"reason":f"changed date to {corrected}","timestamp":datetime.now(),"executed_by":"system"})
                                    logger.info(f"Updated child {child['_id']} date from {child_date} to {corrected}")
                            except ValueError:
                                logger.warning(msg + " and cannot set that day for this month")

        # Continue with standard invalid child cleanup
        remove_invalid_child_demonstrations(demo, next_dates, created_until_date)

        bulk_ops = []
        freezed_children = set(demo.get("freezed_children", []))

        for next_date in next_dates:
            if created_until and next_date <= created_until_date:
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
            if DRY_RUN:
                logger.info(f"DRY RUN: would bulk_write {len(bulk_ops)} ops for parent {demo['_id']}")
            else:
                result = demonstrations_collection.bulk_write(bulk_ops)
                logger.info(f"Processed {result.upserted_count} demos for parent {demo['_id']}")

        # Update created_until
        if next_dates:
            d = RecurringDemonstration.from_dict(demo)
            old_created_until = d.created_until
            d.created_until = next_dates[-1]
            if DRY_RUN:
                logger.info(f"DRY RUN: would update created_until for parent {demo['_id']} from {old_created_until} to {d.created_until}")
                runtime_actions.append({"action":"update","document":d.to_dict(),"old_document":RecurringDemonstration.from_dict(demo).to_dict(),"reason":f"DRY_RUN created_until would be updated from {old_created_until} to {d.created_until}","timestamp":datetime.now(),"executed_by":"system"})
            else:
                d.save()
                runtime_actions.append({"action":"update","document":d.to_dict(),"old_document":RecurringDemonstration.from_dict(demo).to_dict(),"reason":f"created_until updated from {old_created_until} to {d.created_until}","timestamp":datetime.now(),"executed_by":"system"})

    except Exception as e:
        logger.error(f"Error processing demo {demo.get('_id')}: {e}")
        logger.error(format_exc())
    
    finally:
        if not only_calculate:
            update_parent_stats(demo["_id"])


def handle_repeating_demonstrations(only_calculate: bool = False):
    demos = recu_demos_collection.find()
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(process_demo, demo, only_calculate) for demo in demos]
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

    if DRY_RUN:
        logger.info(f"DRY RUN: runtime actions (would be logged): {runtime_actions}")
        logger.info(f"DRY RUN: would update runtimes[{RUNTIME_ID}] status to completed with end_time={datetime.now()}")
    else:
        if runtime_actions:
            runtime_log_collection.insert_many(runtime_actions)
        runtimes_collection.update_one({"_id": RUNTIME_ID},{"$set":{"end_time":datetime.now(),"status":"completed"}})



def main():
    """
    Entry point for processing recurring demonstrations.

    Returns
    -------
    None
    """
    global DRY_RUN
    parser = argparse.ArgumentParser(description="Process recurring demonstrations")
    parser.add_argument("--dry-run", action="store_true", help="Do not write changes to the database; only simulate")
    parser.add_argument("--only-calculate", action="store_true", help="Only calculate next occurrences without creating or deleting demos")
    # Ignore the first two arguments passed to the process (drop argv[0] and argv[1])
    import sys
    args_to_parse = sys.argv[3:]
    args = parser.parse_args(args_to_parse)
    
    print(f"DRY RUN: {args.dry_run}, want to continue? (y/n)")
    answer = input().strip().lower()
    if answer != 'y':
        logger.info("Aborting demonstration processing.")
        return
    
    DRY_RUN = bool(args.dry_run)
    only_calculate = bool(args.only_calculate)

    logger.info(f"Starting demonstration processing. DRY_RUN={DRY_RUN}, ONLY_CALCULATE={only_calculate}")
    handle_repeating_demonstrations(only_calculate=only_calculate)

    if not only_calculate:
        total_merged = merge_duplicates()
        logger.info(f"Total duplicates merged: {total_merged}")
        process_runtime_actions()
    else:
        logger.info("ONLY_CALCULATE flag set: skipped creation, deletion, and merge.")


if __name__ == "__main__":
    main()

