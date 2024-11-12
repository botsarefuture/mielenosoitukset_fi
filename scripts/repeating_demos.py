import logging
from pymongo import MongoClient, UpdateOne
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from config import Config
from utils import DATE_FORMAT

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Establish connection to MongoDB
client = MongoClient(Config.MONGO_URI)
db = client["mielenosoitukset"]
collection = db["demonstrations"]

# Map day names to their corresponding weekday numbers
DAY_NAME_TO_NUM = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def calculate_next_dates(demo_date, repeat_schedule):
    frequency = repeat_schedule.get("frequency")
    interval = repeat_schedule.get("interval", 1)  # Default to every 1 unit
    current_date = datetime.now()
    next_dates = []

    # Determine the end date for the schedule generation (e.g., 1 year from now)
    end_date = current_date + relativedelta(years=1)

    # Generate dates based on the frequency
    while demo_date <= end_date:
        if frequency == "daily":
            next_dates.append(demo_date)
            demo_date += timedelta(days=interval)
        elif frequency == "weekly":
            next_dates.append(demo_date)
            demo_date += timedelta(weeks=interval)
        elif frequency == "monthly":
            next_dates.append(demo_date)
            demo_date += relativedelta(months=interval)
        elif frequency == "yearly":
            next_dates.append(demo_date)
            demo_date += relativedelta(years=interval)

    return next_dates


def handle_repeating_demonstrations():
    try:
        # Find all repeating demonstrations that need to be processed
        repeating_demos = collection.find({"repeating": True})

        # Prepare bulk operations list
        bulk_operations = []

        for demo in repeating_demos:
            try:
                # Parse the current demonstration's date
                demo_date = datetime.strptime(demo["date"], DATE_FORMAT)
                repeat_schedule = demo.get("repeat_schedule", {})

                # Calculate the next dates based on the repeat schedule
                next_dates = calculate_next_dates(demo_date, repeat_schedule)

                for next_date in next_dates:
                    next_date_str = next_date.strftime(DATE_FORMAT)

                    # Check if a document with the same date and parent already exists
                    existing_demo = collection.find_one(
                        {"date": next_date_str, "parent": demo["_id"]}
                    )

                    if existing_demo:
                        # If an existing document is found, update it if it is older
                        if (
                            existing_demo.get("created_datetime", datetime.min)
                            < datetime.now()
                        ):
                            update_operation = {
                                "title": demo["title"],
                                "start_time": demo["start_time"],
                                "end_time": demo["end_time"],
                                "topic": demo["topic"],
                                "facebook": demo["facebook"],
                                "city": demo["city"],
                                "address": demo["address"],
                                "type": demo["type"],
                                "route": demo["route"],
                                "organizers": demo["organizers"],
                                "approved": demo.get(
                                    "approved", False
                                ),  # Copy approved status from parent
                                "linked_organizations": demo["linked_organizations"],
                                "repeating": demo["repeating"],
                                "repeat_schedule": repeat_schedule,  # Keep the repeating schedule
                                "created_datetime": datetime.now(),  # Update creation date
                            }
                            bulk_operations.append(
                                UpdateOne(
                                    {"_id": existing_demo["_id"]},
                                    {"$set": update_operation},
                                )
                            )
                    else:
                        # Prepare a new demonstration for the next scheduled date
                        new_demo = {
                            "title": demo["title"],
                            "date": next_date_str,
                            "start_time": demo["start_time"],
                            "end_time": demo["end_time"],
                            "topic": demo["topic"],
                            "facebook": demo["facebook"],
                            "city": demo["city"],
                            "address": demo["address"],
                            "type": demo["type"],
                            "route": demo["route"],
                            "organizers": demo["organizers"],
                            "approved": demo.get(
                                "approved", False
                            ),  # Copy approved status from parent
                            "linked_organizations": demo["linked_organizations"],
                            "parent": demo[
                                "_id"
                            ],  # Tagging the new demo with the parent demo's ID
                            "repeating": demo["repeating"],
                            "repeat_schedule": repeat_schedule,  # Keep the repeating schedule
                            "created_datetime": datetime.now(),  # Set creation date
                        }

                        # Add the new demonstration as an insert operation
                        bulk_operations.append(
                            UpdateOne(
                                {"date": next_date_str, "parent": demo["_id"]},
                                {"$setOnInsert": new_demo},
                                upsert=True,
                            )
                        )

            except Exception as e:
                logger.error(f"Error processing demonstration {demo.get('_id')}: {e}")

        # Execute bulk operations if there are any
        if bulk_operations:
            result = collection.bulk_write(bulk_operations)
            logger.info(
                f"Upserted {result.upserted_count} new or updated demonstrations."
            )
        else:
            logger.info("No new demonstrations were created or updated.")

    except Exception as e:
        logger.error(f"Error handling repeating demonstrations: {e}")


def find_duplicates():
    try:
        # Aggregation pipeline to find duplicates based on the specified fields
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

        duplicates = collection.aggregate(pipeline)
        return duplicates

    except Exception as e:
        logger.error(f"Error finding duplicates: {e}")
        return []


def remove_duplicates():
    try:
        duplicates = find_duplicates()
        removed_count = 0

        for duplicate in duplicates:
            try:
                ids_to_keep = [duplicate["ids"][0]]  # Keep the first occurrence
                ids_to_remove = duplicate["ids"][1:]  # All others are duplicates

                # Remove duplicate documents
                result = collection.delete_many({"_id": {"$in": ids_to_remove}})
                removed_count += result.deleted_count
                logger.info(f"Removed {result.deleted_count} duplicate demonstrations.")

            except Exception as e:
                logger.error(
                    f"Error removing duplicates with ids {duplicate['ids']}: {e}"
                )

        return removed_count

    except Exception as e:
        logger.error(f"Error removing duplicates: {e}")
        return 0


def main():
    logger.info(
        "Starting the process of handling repeating demonstrations and removing duplicates."
    )

    # Handle repeating demonstrations
    handle_repeating_demonstrations()

    # Remove duplicates after adding new demonstrations
    removed_count = remove_duplicates()
    logger.info(f"Removed {removed_count} duplicate demonstrations.")


if __name__ == "__main__":
    main()
