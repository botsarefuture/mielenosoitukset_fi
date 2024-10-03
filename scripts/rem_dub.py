import os, importlib, sys

# Get the parent directory
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)

database_manager = importlib.import_module("database_manager")
DatabaseManager = database_manager.DatabaseManager

def hide_duplicates():
    # Initialize the database connection
    mongo = DatabaseManager().get_instance().get_db()
    demonstrations = mongo.demonstrations

    # Create a set to keep track of unique documents
    unique_docs = set()
    duplicates = []

    # Retrieve all documents from the collection
    for doc in demonstrations.find():
        # Create a unique identifier for the document
        title = doc.get('title')
        date = doc.get('date')
        start_time = doc.get('start_time', '')[:2]  # Get the first two characters
        city = doc.get('city')
        
        # Combine fields into a unique identifier
        unique_id = (title, date, start_time, city)
        
        if unique_id in unique_docs:
            duplicates.append(doc['_id'])  # Store duplicate document IDs
        else:
            unique_docs.add(unique_id)

    # Hide duplicates
    if duplicates:
        demonstrations.update_many(
            {'_id': {'$in': duplicates}},
            {'$set': {'approved': False, 'hide': True}}
        )
        print(f"Hid {len(duplicates)} duplicate documents.")
    else:
        print("No duplicates found.")

if __name__ == "__main__":
    hide_duplicates()
