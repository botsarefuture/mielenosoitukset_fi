import logging
from pymongo import MongoClient, UpdateOne
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from config import Config

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Establish connection to MongoDB
db = MongoClient(Config.MONGO_URI)
client = db["mielenosoitukset"]
recu_demos_collection = client["recu_demos"]  # Load from recu_demos
demonstrations_collection = client["demonstrations"]  # For saving child demos


def calculate_next_dates(demo_date, repeat_schedule):
    frequency = repeat_schedule.get("frequency")
    interval = repeat_schedule.get("interval", 1)
    current_date = datetime.now()
    next_dates = []

    end_date = current_date + relativedelta(years=1)

    while demo_date <= end_date:
        next_dates.append(demo_date)
        if frequency == "daily":
            demo_date += timedelta(days=interval)
        elif frequency == "weekly":
            demo_date += timedelta(weeks=interval)
        elif frequency == "monthly":
            demo_date += relativedelta(months=interval)
        elif frequency == "yearly":
            demo_date += relativedelta(years=interval)

    return next_dates


def handle_repeating_demonstrations():
    try:
        repeating_demos = recu_demos_collection.find()
        bulk_operations = []

        for demo in repeating_demos:
            try:
                demo_date = datetime.strptime(demo["date"], "%d.%m.%Y")
                repeat_schedule = demo.get("repeat_schedule", {})
                created_until = demo.get(
                    "created_until", datetime.min
                )  # Load created_until
                if created_until is None:
                    created_until = datetime.now()
                next_dates = calculate_next_dates(demo_date, repeat_schedule)

                for next_date in next_dates:
                    if next_date <= created_until:
                        continue  # Skip dates that have already been created

                    next_date_str = next_date.strftime("%d.%m.%Y")

                    existing_demo = demonstrations_collection.find_one(
                        {"date": next_date_str, "parent": demo["_id"]}
                    )

                    if existing_demo:
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
                                "approved": demo.get("approved", False),
                                "linked_organizations": demo["linked_organizations"],
                                "repeating": demo["repeating"],
                                "repeat_schedule": repeat_schedule,
                                "created_datetime": datetime.now(),
                            }
                            bulk_operations.append(
                                UpdateOne(
                                    {"_id": existing_demo["_id"]},
                                    {"$set": update_operation},
                                )
                            )
                    else:
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
                            "organizers": demo.get("organizers", []),
                            "approved": demo.get("approved", False),
                            "linked_organizations": demo["linked_organizations"],
                            "parent": demo["_id"],  # Save parent ID
                            "recurring": True,
                            "created_datetime": datetime.now(),
                        }

                        # Save the new demonstration to the demonstrations collection
                        bulk_operations.append(
                            UpdateOne(
                                {"date": next_date_str, "parent": demo["_id"]},
                                {"$setOnInsert": new_demo},
                                upsert=True,
                            )
                        )

            except Exception as e:
                logger.error(f"Error processing demonstration {demo.get('_id')}: {e}")

        if bulk_operations:
            result = demonstrations_collection.bulk_write(bulk_operations)
            logger.info(
                f"Upserted {result.upserted_count} new or updated demonstrations."
            )
        else:
            logger.info("No new demonstrations were created or updated.")

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
            try:
                ids_to_keep = [duplicate["ids"][0]]
                ids_to_remove = duplicate["ids"][1:]

                result = demonstrations_collection.delete_many(
                    {"_id": {"$in": ids_to_remove}}
                )
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

    handle_repeating_demonstrations()
    removed_count = remove_duplicates()
    logger.info(f"Removed {removed_count} duplicate demonstrations.")


if __name__ == "__main__":
    main()
