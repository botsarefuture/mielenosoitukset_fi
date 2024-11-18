import os
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pymongo import MongoClient, UpdateOne
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from config import Config
from classes import Demonstration, RecurringDemonstration

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Establish connection to MongoDB
client = MongoClient(os.getenv("MONGO_URI", Config.MONGO_URI))
db = client["mielenosoitukset"]
recu_demos_collection = db["recu_demos"]
demonstrations_collection = db["demonstrations"]

def calculate_next_dates(demo_date, repeat_schedule):
    frequency = repeat_schedule.get("frequency")
    interval = repeat_schedule.get("interval", 1)
    current_date = datetime.now()
    next_dates = []

    end_date = current_date + relativedelta(years=1)

    while demo_date <= end_date:
        if demo_date >= current_date:
            next_dates.append(demo_date)

        if frequency == "daily":
            demo_date += timedelta(days=interval)
        elif frequency == "weekly":
            demo_date += timedelta(weeks=interval)
        elif frequency == "monthly":
            demo_date += relativedelta(months=interval)
        elif frequency == "yearly":
            demo_date += relativedelta(years=interval)
        else:
            break
    logger.debug(f"Next dates calculated: {next_dates}")
    return next_dates

def remove_invalid_child_demonstrations(parent_demo, valid_dates):
    try:
        valid_date_strings = {d.strftime("%d.%m.%Y") for d in valid_dates if isinstance(d, datetime)}
        child_demos = demonstrations_collection.find({"parent": parent_demo["_id"]})

        for demo in child_demos:
            if demo["date"] not in valid_date_strings:
                demonstrations_collection.delete_one({"_id": demo["_id"]})
                logger.info(f"Removed demonstration with id {demo['_id']} due to invalid date.")
    except Exception as e:
        logger.error(f"Error removing invalid child demonstrations for parent {parent_demo['_id']}: {e}")

def process_demo(demo):
    try:
        demo_date = datetime.strptime(demo["date"], "%d.%m.%Y")
        repeat_schedule = demo.get("repeat_schedule", {})
        created_until = demo.get("created_until")
        if created_until:
            created_until = datetime.strptime(created_until, "%d.%m.%Y")
        else:
            created_until = datetime.min

        next_dates = calculate_next_dates(demo_date, repeat_schedule)

        remove_invalid_child_demonstrations(demo, next_dates)

        bulk_operations = []
        for next_date in next_dates:
            if next_date <= created_until:
                logger.debug(f"Skipping {next_date} because it is before {created_until}")
                continue

            next_date_str = next_date.strftime("%d.%m.%Y")
            existing_demo = demonstrations_collection.find_one({"date": next_date_str, "parent": demo["_id"]})

            if existing_demo:
                update_demo = RecurringDemonstration(**demo)
                update_data = update_demo.to_dict()
                if "_id" in update_data:
                    del update_data["_id"]
                bulk_operations.append(
                    UpdateOne({"date": next_date_str, "parent": demo["_id"]}, {"$set": update_data}, upsert=True)
                )
            else:
                new_demo_data = demo.copy()
                new_demo_data["date"] = next_date_str
                new_demo_data["parent"] = demo["_id"]
                new_demo_data["recurring"] = True
                new_demo_data.pop("created_until", None)
                new_demo_data.pop("_id", None)
                new_demo = Demonstration(**new_demo_data)

                bulk_operations.append(
                    UpdateOne({"date": next_date_str, "parent": demo["_id"]}, {"$setOnInsert": new_demo.to_dict()}, upsert=True)
                )

        if bulk_operations:
            result = demonstrations_collection.bulk_write(bulk_operations)
            logger.info(f"Upserted {result.upserted_count} new or updated demonstrations for demo {demo['_id']}.")
    except Exception as e:
        logger.error(f"Error processing demonstration {demo.get('_id')}: {e}")

def handle_repeating_demonstrations():
    try:
        repeating_demos = recu_demos_collection.find()
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(process_demo, demo) for demo in repeating_demos]
            for future in as_completed(futures):
                future.result()
    except Exception as e:
        logger.error(f"Error handling repeating demonstrations: {e}")

def find_duplicates():
    try:
        pipeline = [
            {
                "$group": {
                    "_id": {
                        "title": "$title",
                        "organizers": "$organizers",
                        "date": "$date",
                        "start_time": "$start_time",
                        "end_time": "$end_time",
                        "address": "$address",
                        "city": "$city",
                    },
                    "count": {"$sum": 1},
                    "ids": {"$push": "$_id"},
                }
            },
            {"$match": {"count": {"$gt": 1}}},
        ]

        duplicates = demonstrations_collection.aggregate(pipeline)
        return duplicates

    except Exception as e:
        logger.error(f"Error finding duplicates: {e}")
        return []

def remove_duplicates():
    try:
        duplicates = find_duplicates()
        removed_count = 0

        for duplicate in duplicates:
            ids_to_remove = duplicate["ids"][1:]
            if ids_to_remove:
                try:
                    result = demonstrations_collection.delete_many({"_id": {"$in": ids_to_remove}})
                    removed_count += result.deleted_count
                    logger.info(f"Removed {result.deleted_count} duplicate demonstrations.")
                except Exception as e:
                    logger.error(f"Error removing duplicates with ids {duplicate['ids']}: {e}")

        return removed_count

    except Exception as e:
        logger.error(f"Error removing duplicates: {e}")
        return 0

def main():
    logger.info("Starting the process of handling repeating demonstrations and removing duplicates.")
    handle_repeating_demonstrations()
    removed_count = remove_duplicates()
    logger.info(f"Removed {removed_count} duplicate demonstrations.")

if __name__ == "__main__":
    main()
