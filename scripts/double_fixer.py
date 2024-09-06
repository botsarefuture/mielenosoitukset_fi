from pymongo import MongoClient
from config import Config

# Establish connection to MongoDB
client = MongoClient(Config.MONGO_URI)
db = client["mielenosoitukset"]
collection = db["demonstrations"]


def find_duplicates():
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


def remove_duplicates():
    duplicates = find_duplicates()
    removed_count = 0

    for duplicate in duplicates:
        ids_to_keep = [duplicate["ids"][0]]  # Keep the first occurrence
        ids_to_remove = duplicate["ids"][1:]  # All others are duplicates

        # Remove duplicate documents
        result = collection.delete_many({"_id": {"$in": ids_to_remove}})
        removed_count += result.deleted_count

    return removed_count


def main():
    removed_count = remove_duplicates()
    print(f"Removed {removed_count} duplicate demonstrations.")


if __name__ == "__main__":
    main()
