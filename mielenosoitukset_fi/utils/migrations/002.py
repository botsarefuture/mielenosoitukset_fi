from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
import re
from mielenosoitukset_fi.utils.database import get_database_manager
from mielenosoitukset_fi.utils.classes.Demonstration import Demonstration, is_none, RepeatSchedule

DB = get_database_manager()

def generate_slug(title):
    """
    Generate a URL-friendly slug from the demo title.
    Converts to lowercase, replaces spaces with '-', removes invalid characters.
    """
    if not title:
        return None
    slug = title.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)  # remove non-alphanumeric characters
    slug = re.sub(r"\s+", "-", slug.strip())  # replace spaces with dash
    return slug

def get_unique_slug(base_slug, existing_slugs, slug_counts):
    """
    Ensure the slug is unique.
    - existing_slugs: set of slugs already found in the DB
    - slug_counts: dict tracking how many times each base slug was used in this migration
    """
    if base_slug is None:
        return None

    # if it already exists in DB or has been seen before, increment counter
    count = slug_counts.get(base_slug, 0) + 1
    slug_counts[base_slug] = count

    if count == 1 and base_slug not in existing_slugs:
        existing_slugs.add(base_slug)
        return base_slug

    # otherwise append running number
    unique_slug = f"{base_slug}-{count}"
    while unique_slug in existing_slugs:
        count += 1
        slug_counts[base_slug] = count
        unique_slug = f"{base_slug}-{count}"

    existing_slugs.add(unique_slug)
    return unique_slug

def get_next_running_number():
    """
    Get the next running number by finding the max existing running_number.
    """
    last_demo = DB["demonstrations"].find_one(sort=[("running_number", -1)])
    if last_demo and last_demo.get("running_number") is not None:
        return last_demo["running_number"] + 1
    return 1

def migrate_demonstrations():
    demos = DB["demonstrations"].find({})
    existing_slugs = {d["slug"] for d in DB["demonstrations"].find({"slug": {"$exists": True, "$ne": None}}, {"slug": 1})}
    slug_counts = {}

    for demo in demos:
        demo_id = demo["_id"]
        updated_fields = {}
        changed = False

        # --- Date conversion ---
        date_str = demo.get("date")
        if date_str:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                try:
                    dt = datetime.strptime(date_str, "%d.%m.%Y")
                    updated_fields["date"] = dt.date().isoformat()
                    changed = True
                except ValueError:
                    print(f"[Warning] Invalid date format for demo {demo_id}: {date_str}")

        # --- Time conversion ---
        for field in ["start_time", "end_time"]:
            time_str = demo.get(field)
            if time_str:
                try:
                    if time_str.count(":") == 1:
                        dt = datetime.strptime(time_str, "%H:%M")
                        updated_fields[field] = dt.time().replace(second=0).isoformat()
                        changed = True
                    else:
                        dt = datetime.strptime(time_str, "%H:%M:%S")
                        updated_fields[field] = dt.time().isoformat()
                        changed = True
                except ValueError:
                    print(f"[Warning] Invalid time format for demo {demo_id} field {field}: {time_str}")

        # --- Aliases conversion ---
        aliases = demo.get("aliases") or []
        new_aliases = []
        for alias in aliases:
            if not isinstance(alias, ObjectId):
                try:
                    new_aliases.append(ObjectId(alias))
                    changed = True
                except:
                    new_aliases.append(alias)
            else:
                new_aliases.append(alias)
        updated_fields["aliases"] = new_aliases

        # --- Preview image fix ---
        preview_image = demo.get("preview_image")
        if preview_image and preview_image.startswith("/static/demo_preview/"):
            updated_fields["preview_image"] = "https://mielenosoitukset.fi" + preview_image
            changed = True

        img = demo.get("img")
        
        cover_picture = demo.get("cover_picture")
        
        if not cover_picture:
            if img:
                updated_fields["cover_picture"] = img
                updated_fields["cover_source"] = "user"
            
            elif preview_image:
                updated_fields["cover_picture"] = preview_image
                updated_fields["cover_source"] = "auto"
            

        # --- Recurring demo fix ---
        parent_id = demo.get("parent")
        if parent_id and not demo.get("recurs", False):
            updated_fields["recurs"] = True
            parent_doc = DB["recu_demos"].find_one({"_id": ObjectId(parent_id)})
            if parent_doc:
                try:
                    updated_fields["repeat_schedule"] = RepeatSchedule.from_dict(parent_doc.get("repeat_schedule", {})).to_dict()
                except Exception as e:
                    print(f"[Warning] Could not convert repeat_schedule for demo {demo_id}: {e}")
            changed = True

        # --- Running number & slug ---
        if demo.get("running_number") is None:
            updated_fields["running_number"] = get_next_running_number()
            changed = True

        title = demo.get("title")
        if not demo.get("slug"):
            base_slug = generate_slug(title)
            unique_slug = get_unique_slug(base_slug, existing_slugs, slug_counts)
            updated_fields["slug"] = unique_slug
            changed = True

        # --- Merged into ---
        if "merged_into" not in demo:
            updated_fields["merged_into"] = None
            changed = True

        if changed:
            DB["demonstrations"].update_one({"_id": demo_id}, {"$set": updated_fields})
            print(f"[Info] Updated demo {demo_id} -> {updated_fields}")

if __name__ == "__main__":
    migrate_demonstrations()
