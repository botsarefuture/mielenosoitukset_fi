from mielenosoitukset_fi.utils.cities import normalize_city_key
from mielenosoitukset_fi.utils.database import get_database_manager


def migrate_city_keys(db=None):
    """Backfill normalized city keys for city-scoped admin permissions."""
    db = db if db is not None else get_database_manager()
    results = {}

    for collection_name in ("demonstrations", "recu_demos"):
        updated = 0
        for doc in db[collection_name].find({}, {"city": 1, "city_key": 1}):
            city_key = normalize_city_key(doc.get("city"))
            if not city_key or doc.get("city_key") == city_key:
                continue
            db[collection_name].update_one(
                {"_id": doc["_id"]},
                {"$set": {"city_key": city_key}},
            )
            updated += 1
        results[collection_name] = updated
        print(f"Updated {updated} documents in {collection_name}.")

    return results


if __name__ == "__main__":
    migrate_city_keys()
