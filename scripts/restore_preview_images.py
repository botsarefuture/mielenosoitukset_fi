"""Revert the 2026-11-11 preview image regeneration (PR #1090).

Reads the backup written by regenerate_previews.py (JSON lines: _id, old, new)
and sets each demonstration's `preview_image` back to its value from before the
first regeneration. An event is skipped when its `preview_image` no longer
matches a URL that the regeneration wrote, so later edits are never overwritten.
The old CDN objects were never deleted or overwritten (every upload got a new
key), so the old URLs still work.

    cd /var/www/mielenosoitukset_fi
    sudo -u www-data env PYTHONPATH=. python3 /var/backups/mielenosoitukset/restore_preview_images.py \
        /var/backups/mielenosoitukset/preview_image_backup_2026-11-11.jsonl            # dry run
    ... same command with --apply                                                     # write
"""

import argparse
import json
import sys

from bson import ObjectId
from config import Config

Config.ENABLE_BACKGROUND_JOBS = False
Config.DISABLE_BACKGROUND_JOBS = True
Config.ENABLE_PANIC_THREAD = False

from mielenosoitukset_fi.app import create_app  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("backup")
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    args = parser.parse_args()

    original, written = {}, {}
    with open(args.backup, encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            original.setdefault(row["_id"], row["old"])  # first entry = value before any run
            written.setdefault(row["_id"], set()).add(row["new"])

    app = create_app()
    restored = skipped = 0
    with app.app_context():
        from mielenosoitukset_fi.database_manager import DatabaseManager

        demos = DatabaseManager().get_instance().get_db()["demonstrations"]
        for demo_id, old in original.items():
            current = (demos.find_one({"_id": ObjectId(demo_id)}, {"preview_image": 1}) or {}).get("preview_image")
            if current not in written[demo_id]:
                skipped += 1
                print(f"skip {demo_id}: preview_image changed since regeneration ({current})")
                continue
            if args.apply:
                demos.update_one({"_id": ObjectId(demo_id), "preview_image": current},
                                 {"$set": {"preview_image": old}})
            restored += 1
    print(json.dumps({"mode": "apply" if args.apply else "dry-run", "restored": restored, "skipped": skipped}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
