"""Throttled regeneration of demonstration preview images (PR #1090).

Run ON PRODUCTION from /var/www/mielenosoitukset_fi with the app's Python, after
the deploy that contains PR #1090 is live (check https://mielenosoitukset.fi/health
reports the merge SHA):

    cd /var/www/mielenosoitukset_fi
    sudo -u www-data env PYTHONPATH=. python3 scripts/regenerate_preview_images.py --limit 3            # sample: 3 upcoming events
    sudo -u www-data env PYTHONPATH=. python3 scripts/regenerate_preview_images.py --all --delay 0.5    # full run

Uses the same code path as the `run_preview` job: create_screenshot(return_bytes=True)
-> upload_image_fileobj(bucket, ..., "demo_preview") -> $set preview_image.
Each upload creates a NEW CDN object (DEM/demo_preview-N.jpg); old objects stay,
so rollback = restore the old URLs from the backup file this script writes.
Touches only the `preview_image` field of `demonstrations`.
"""

import argparse
import io
import json
import sys
import time
from datetime import date

from config import Config

# A one-off process must not start the scheduler or the panic thread.
Config.ENABLE_BACKGROUND_JOBS = False
Config.DISABLE_BACKGROUND_JOBS = True
Config.ENABLE_PANIC_THREAD = False

from mielenosoitukset_fi.app import create_app  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="include past events")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--delay", type=float, default=0.5, help="seconds between uploads")
    parser.add_argument("--backup", default=f"/var/tmp/preview_image_backup_{date.today()}.jsonl")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        from mielenosoitukset_fi.database_manager import DatabaseManager
        from mielenosoitukset_fi.utils.s3 import upload_image_fileobj
        from mielenosoitukset_fi.utils.screenshot import create_screenshot

        demos = DatabaseManager().get_instance().get_db()["demonstrations"]
        query = {} if args.all else {"in_past": False}
        cursor = demos.find(query, {"_id": 1, "preview_image": 1}).sort("date", 1)
        if args.limit:
            cursor = cursor.limit(args.limit)
        ids = list(cursor)
        bucket = getattr(Config, "S3_BUCKET", "mielenosoitukset.fi")
        done = failed = 0
        failures = []
        with open(args.backup, "a", encoding="utf-8") as backup:
            for row in ids:
                demo_id = row["_id"]
                demo = demos.find_one({"_id": demo_id})
                png = create_screenshot(demo, return_bytes=True)
                if not png:
                    failed += 1
                    failures.append((str(demo_id), "render"))
                    continue
                url = upload_image_fileobj(bucket, io.BytesIO(png), f"{demo_id}.png", "demo_preview")
                if not url:
                    failed += 1
                    failures.append((str(demo_id), "upload"))
                    continue
                backup.write(json.dumps({"_id": str(demo_id), "old": row.get("preview_image"), "new": url}) + "\n")
                backup.flush()
                demos.update_one({"_id": demo_id}, {"$set": {"preview_image": url}})
                done += 1
                print(f"ok {demo_id} -> {url}", flush=True)
                time.sleep(args.delay)
        print(json.dumps({"selected": len(ids), "done": done, "failed": failed,
                          "skipped": len(ids) - done - failed, "failures": failures,
                          "backup": args.backup}))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
