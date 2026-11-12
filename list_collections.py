#!/usr/bin/env python
"""
Script to list all collections in the database.
"""

from mielenosoitukset_fi.database_manager import DatabaseManager

def list_collections():
    """List all collections in the database."""
    db = DatabaseManager().get_instance().get_db()
    
    collections = db.list_collection_names()
    
    print(f"Found {len(collections)} collections in database:")
    for col in sorted(collections):
        count = db[col].count_documents({})
        print(f"  - {col:<40} ({count} documents)")

if __name__ == "__main__":
    list_collections()
