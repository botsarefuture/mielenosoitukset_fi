from pymongo import UpdateOne
from mielenosoitukset_fi.database_manager import DatabaseManager

def migrate():
    print("meow")
    db_man = DatabaseManager.get_instance()
    DB = db_man.get_db()

    bulk_updates = []

    for demo in DB["demonstrations"].find({}):
        print(demo)
        update_fields = {}
        unset_fields = {}

        # 1️⃣ Topic -> tags
        if "topic" in demo and isinstance(demo.get("topic"), str):
            tags = demo.get("tags", [])
            if len(tags) == 0:
                tags.append(demo["topic"].lower())
            update_fields["tags"] = tags

        if "topic" in demo:
            unset_fields["topic"] = ""
            
        if "repeat_schedule" in demo:
            unset_fields["repeat_schedule"] = ""

        # 2️⃣ repeating / recurring -> recurs
        recurs = demo.get("repeating") or demo.get("recurring") or False
        update_fields["recurs"] = bool(recurs)
        unset_fields["repeating"] = ""
        unset_fields["recurring"] = ""

        # 3️⃣ type + event_type -> event_type
        if "type" in demo:
            update_fields["event_type"] = demo.get("event_type") or demo["type"]
            unset_fields["type"] = ""

        # 4️⃣ drop save_flag
        if "save_flag" in demo:
            unset_fields["save_flag"] = ""

        if update_fields or unset_fields:
            bulk_updates.append(
                UpdateOne({"_id": demo["_id"]}, {"$set": update_fields, "$unset": unset_fields})
            )

    if bulk_updates:
        result = DB["demonstrations"].bulk_write(bulk_updates)
        print(f"Modified {result.modified_count} recurring demonstrations.")
    else:
        print("No demonstrations required migration.")