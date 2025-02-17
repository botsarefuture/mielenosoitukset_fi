import os
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pymongo import MongoClient, UpdateOne
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta, weekday
from config import Config
from mielenosoitukset_fi.utils.classes import Demonstration, RecurringDemonstration
from traceback import format_exc

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
client = MongoClient(os.getenv("MONGO_URI", Config.MONGO_URI))
db = client["mielenosoitukset"]
recu_demos_collection = db["recu_demos"]
demonstrations_collection = db["demonstrations"]


# Helper function to calculate the next dates
def calculate_next_dates(start_date, schedule):
    """Calculate the next dates for a recurring demonstration based on the schedule.

    Parameters
    ----------
    start_date : datetime
        The start date of the demonstration.
    schedule : dict
        The repeat schedule containing frequency, interval, and other details.

    Returns
    -------
    list of datetime
        The list of next dates for the recurring demonstration.
    """
    frequency = schedule.get("frequency")
    interval = schedule.get("interval", 1)
    current_date = datetime.now()
    next_dates = []

    end_date = current_date + relativedelta(years=1)

    while start_date <= end_date:
        if start_date >= current_date:
            next_dates.append(start_date)
        if frequency == "daily":
            start_date += timedelta(days=interval)
        elif frequency == "weekly":
            start_date += timedelta(weeks=interval)
        elif frequency == "monthly":
            if schedule.get("monthly_option") == "day_of_month":
                start_date += relativedelta(months=interval)
            elif schedule.get("monthly_option") == "nth_weekday":
                nth_weekday = schedule.get("nth_weekday")
                weekday_of_month = schedule.get("weekday_of_month")
                if nth_weekday and weekday_of_month:
                    start_date = start_date + relativedelta(months=interval)
                    start_date = start_date.replace(day=1)
                    weekday_map = {
                        "monday": 0,
                        "tuesday": 1,
                        "wednesday": 2,
                        "thursday": 3,
                        "friday": 4,
                        "saturday": 5,
                        "sunday": 6,
                    }
                    weekday_num = weekday_map[weekday_of_month]
                    nth_weekday_map = {
                        "first": 1,
                        "second": 2,
                        "third": 3,
                        "fourth": 4,
                        "last": -1,
                    }
                    nth = nth_weekday_map[nth_weekday]
                    if nth == -1:
                        start_date = start_date + relativedelta(
                            day=31, weekday=weekday(weekday_num, -1)
                        )
                    else:
                        start_date = start_date + relativedelta(
                            weekday=weekday(weekday_num, nth)
                        )
        elif frequency == "yearly":
            start_date += relativedelta(years=interval)
        else:
            break

    logger.debug(f"Calculated next dates: {next_dates}")
    return next_dates


# Remove invalid child demonstrations
def remove_invalid_child_demonstrations(parent_demo, valid_dates):
    """

    Parameters
    ----------
    parent_demo :
        param valid_dates:
    valid_dates :


    Returns
    -------


    """
    valid_date_strings = {d.strftime("%Y-%m-%d") for d in valid_dates}
    child_demos = demonstrations_collection.find({"parent": parent_demo["_id"]})

    for demo in child_demos:
        if demo["date"] not in valid_date_strings:
            demonstrations_collection.delete_one({"_id": demo["_id"]})
            logger.info(f"Deleted invalid child demonstration {demo['_id']}")


def get(object, key, default=None):
    """

    Parameters
    ----------
    object :
        param key:
    default :
        Default value = None)
    key :


    Returns
    -------


    """
    result = object.get(key, default)
    if result is None:
        return default
    else:
        return result


# Process a single demonstration
def process_demo(demo):
    """

    Parameters
    ----------
    demo :


    Returns
    -------


    """
    try:
        demo_date = datetime.strptime(demo["date"], "%Y-%m-%d")  # modified to ISO-8601
        print(demo_date)
        schedule = demo.get("repeat_schedule", {})
        created_until = datetime.strptime(
            get(demo, "created_until", "1900-01-01"), "%Y-%m-%d"  # modified default and ISO-8601
        )
        print(created_until)

        next_dates = calculate_next_dates(demo_date, schedule)
        remove_invalid_child_demonstrations(demo, next_dates)

        bulk_operations = []
        for next_date in next_dates:
            if next_date <= created_until:
                logger.debug(f"Skipping {next_date} (before {created_until})")
                continue

            next_date_str = next_date.strftime("%Y-%m-%d")  # modified to ISO-8601
            existing_demo = demonstrations_collection.find_one(
                {"date": next_date_str, "parent": demo["_id"]}
            )

            if existing_demo:
                Demonstration(**existing_demo).update_self_from_recurring(
                    RecurringDemonstration(**demo)
                )
            else:
                new_demo_data = demo.copy()
                new_demo_data.update(
                    {
                        "date": next_date_str,
                        "parent": demo["_id"],
                        "recurring": True,
                    }
                )
                new_demo_data.pop("created_until", None)
                new_demo_data.pop("_id", None)
                new_demo = Demonstration(**new_demo_data)

                bulk_operations.append(
                    UpdateOne(
                        {"date": next_date_str, "parent": demo["_id"]},
                        {"$setOnInsert": new_demo.to_dict()},
                        upsert=True,
                    )
                )

        if bulk_operations:
            result = demonstrations_collection.bulk_write(bulk_operations)
            logger.info(
                f"Processed {result.upserted_count} demonstrations for parent {demo['_id']}"
            )
    except Exception as e:
        logger.error(f"Error processing demonstration {demo.get('_id')}: {e}")
        logger.error(format_exc())
        raise RuntimeWarning from e


# Handle all repeating demonstrations
def handle_repeating_demonstrations():
    """ """
    try:
        demos = recu_demos_collection.find()
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(process_demo, demo) for demo in demos]
            for future in as_completed(futures):
                future.result()
    except Exception as e:
        logger.error(f"Error handling repeating demonstrations: {e}")


# Find duplicate demonstrations
def find_duplicates():
    """ """

    def demo_match(demo1, demo2):
        """

        Parameters
        ----------
        demo1 :
            param demo2:
        demo2 :


        Returns
        -------


        """
        return (
            demo1["title"] == demo2["title"]
            and demo1["date"] == demo2["date"]
            and demo1["city"] == demo2["city"]
            and demo1["address"] == demo2["address"]
            and (
                demo1.get("event_type") == demo2.get("event_type")
                or demo1.get("type") == demo2.get("type")
            )
        )

    demos = list(
        demonstrations_collection.find(
            {"hide": False, "in_past": False, "recurring": True}
        )
    )
    duplicates = []

    for i, demo in enumerate(demos):
        duplicate_group = {"ids": [demo["_id"]]}
        for other_demo in demos[i + 1 :]:
            if demo_match(demo, other_demo):
                duplicate_group["ids"].append(other_demo["_id"])

        if len(duplicate_group["ids"]) > 1:
            duplicates.append(duplicate_group)

    return duplicates


# Merge duplicate demonstrations
def merge_duplicates():
    """ """
    duplicates = find_duplicates()
    merged_count = 0

    for group in duplicates:
        ids = group["ids"]
        base_demo = demonstrations_collection.find_one({"_id": ids[0]})
        for duplicate_id in ids[1:]:
            try:
                Demonstration(**base_demo).merge(duplicate_id)
                print("MERGING", duplicate_id)
                merged_count += 1
            except Exception as e:
                logger.error(f"Error merging duplicate {duplicate_id}: {e}")

    logger.info(f"Merged {merged_count} duplicate demonstrations.")
    return merged_count


# Main function
def main():
    """ """
    logger.info("Starting demonstration processing.")
    handle_repeating_demonstrations()
    total_merged = merge_duplicates()
    logger.info(f"Total duplicates merged: {total_merged}")


if __name__ == "__main__":
    main()
