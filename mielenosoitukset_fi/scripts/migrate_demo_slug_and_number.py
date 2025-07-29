"""
Migration script to add running_number and slug fields to all demonstrations.

- running_number: sequential integer, unique
- slug: URL-friendly version of the title, unique (with fallback if duplicate)

Usage:
    python migrate_demo_slug_and_number.py
"""
import re
from bson import ObjectId
from pymongo import MongoClient
from unidecode import unidecode

def slugify(text):
    text = unidecode(text or "")
    text = re.sub(r"[^a-zA-Z0-9\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text).strip("-").lower()
    return text or "demo"

def main():
    client = MongoClient("mongodb://95.216.148.93:27017/")
    db = client.get_database("mielenosoitukset")
    demos = db.demonstrations

    # Find the current max running_number
    max_number = demos.find_one(sort=[("running_number", -1)])
    next_number = (max_number["running_number"] + 1) if max_number and "running_number" in max_number else 1

    # Build a set of used slugs
    used_slugs = set()
    for demo in demos.find({"slug": {"$exists": True}}):
        used_slugs.add(demo["slug"])

    for demo in demos.find():
        updates = {}
        # Assign running_number if missing
        if "running_number" not in demo:
            updates["running_number"] = next_number
            next_number += 1
        # Assign slug if missing
        if "slug" not in demo:
            base_slug = slugify(demo.get("title", "demo"))
            slug = base_slug
            i = 2
            while slug in used_slugs:
                slug = f"{base_slug}-{i}"
                i += 1
            updates["slug"] = slug
            used_slugs.add(slug)
        if updates:
            demos.update_one({"_id": demo["_id"]}, {"$set": updates})
            print(f"Updated demo {_id_str(demo)}: {updates}")

def _id_str(demo):
    return str(demo.get("_id", "?"))

if __name__ == "__main__":
    main()
