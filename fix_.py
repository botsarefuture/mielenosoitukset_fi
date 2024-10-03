from bson import ObjectId
from database_manager import DatabaseManager

# Get the MongoDB database instance
mongo = DatabaseManager().get_instance().get_db()
collection = mongo['demonstrations']  # Select the collection

# Define the criteria and the update
criteria = {
    'repeating': True,
    'parent': ObjectId('66c672b4af8ba803b42aece2')  # ObjectId for the parent
}
update = {
    '$set': {'hide': True, 'approved': False}
}

# Update the documents
result = collection.update_many(criteria, update)

# Print the result
print(f"{result.modified_count} documents were updated.")
