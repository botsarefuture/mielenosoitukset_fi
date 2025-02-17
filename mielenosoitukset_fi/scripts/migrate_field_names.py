#!/usr/bin/env python3
"""
Migration Script to update field names in MongoDB collections.

This script connects to the MongoDB instance and migrates documents by converting
CamelCase field names to snake_case based on a provided mapping.

Example
-------
    Run the script from the command line:
        $ python migrate_field_names.py
"""

from pymongo import MongoClient

def migrate_fields(collection, mapping):
    """
    Migrate field names in the given collection.

    Parameters
    ----------
    collection : pymongo.collection.Collection
        The MongoDB collection to perform migration.
    mapping : dict
        Mapping of old field names (CamelCase) to new field names (snake_case).
    """
    updates = []
    for doc in collection.find():
        update_dict = {}
        for old_field, new_field in mapping.items():
            if old_field in doc:
                update_dict[new_field] = doc.pop(old_field)
        if update_dict:
            updates.append((doc['_id'], update_dict))
    for doc_id, upd in updates:
        collection.update_one({'_id': doc_id}, {'$set': upd})
        print(f"Updated document {doc_id} with {upd}")

def main():
    """
    Main function to run the migration.

    Connects to the MongoDB instance and migrates the specified collections.
    """
    # Connect to MongoDB (adjust the connection string and database name as needed)
    client = MongoClient('mongodb://localhost:27017/')
    db = client['mielenosoitukset_fi_db']  # Change database name if required

    # Specify field mappings for each collection
    demo_mapping = {
        'startTime': 'start_time',
        'endTime': 'end_time',
        'linkedOrganizations': 'linked_organizations'
    }
    recu_demo_mapping = {
        'startTime': 'start_time',
        'endTime': 'end_time',
    }

    print("Migrating 'demonstrations' collection...")
    demos = db['demonstrations']
    migrate_fields(demos, demo_mapping)

    print("Migrating 'recu_demos' collection...")
    recu_demos = db['recu_demos']
    migrate_fields(recu_demos, recu_demo_mapping)

    print("Migration completed.")

if __name__ == '__main__':
    main()
