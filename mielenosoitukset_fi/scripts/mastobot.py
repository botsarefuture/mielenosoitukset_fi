"""mastobot: automated Mastodon poster for mielenosoitukset.fi events

This script fetches events from the site API and posts new upcoming
demonstrations to Mastodon. It is non-interactive, configurable via
environment variables and CLI flags, and suitable to run as a service
or from cron.

Features added:
- Read Mastodon credentials from environment (no hard-coded secrets)
- Dry-run mode (no network posting)
- Retry/backoff for HTTP requests
- Proper pagination collection
- Robust date parsing (uses dateutil if available)
- CLI options: interval, once, dry-run, max-days, data-file, log-level
- Logging instead of prints

TODO:
- Implement automated running in a thread, that runs via the app.py.
- Add error handling and logging for the thread.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import sys
import time
from typing import Iterable, List, Optional, Set

import requests
from mastodon import Mastodon, MastodonError

try:
    from dateutil import parser as dateutil_parser  # type: ignore
except Exception:
    dateutil_parser = None


# -- Defaults / environment -----------------------------------------------
DEFAULT_API_URL = os.getenv(
    "MO_API_URL", "https://mielenosoitukset.fi/api/demonstrations"
)
DEFAULT_MASTODON_BASE = os.getenv("MASTODON_API_BASE", "https://mastodon.social")
DEFAULT_DATA_FILE = os.getenv("MO_POSTED_FILE", "posted_events.txt")
DEFAULT_MAX_DAYS = int(os.getenv("MO_POST_MAX_DAYS", "60"))
DEFAULT_CHECK_INTERVAL = int(os.getenv("MO_CHECK_INTERVAL", "3600"))


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_posted(data_file: str) -> Set[str]:
    if not os.path.exists(data_file):
        return set()
    with open(data_file, "r", encoding="utf8") as f:
        return {line.strip() for line in f if line.strip()}


def append_posted(data_file: str, link: str) -> None:
    with open(data_file, "a", encoding="utf8") as f:
        f.write(link + "\n")


def parse_event_date(date_str: Optional[str]) -> Optional[datetime.datetime]:
    if not date_str:
        return None
    # Prefer dateutil if available for flexible parsing
    if dateutil_parser:
        try:
            return dateutil_parser.parse(date_str)
        except Exception:
            pass
    # Try ISO formats
    try:
        return datetime.datetime.fromisoformat(date_str)
    except Exception:
        pass
    # Common fallback YYYY-MM-DD
    try:
        return datetime.datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        logging.debug("Failed to parse date string: %s", date_str)
        return None


def format_finnish_date(dt: datetime.datetime) -> str:
    months_fi = [
        "tammikuuta",
        "helmikuuta",
        "maaliskuuta",
        "huhtikuuta",
        "toukokuuta",
        "kesäkuuta",
        "heinäkuuta",
        "elokuuta",
        "syyskuuta",
        "lokakuuta",
        "marraskuuta",
        "joulukuuta",
    ]
    day = dt.day
    month = months_fi[dt.month - 1]
    year = dt.year
    hour = dt.hour
    minute = dt.minute
    if hour == 0 and minute == 0:
        return f"{day}. {month} {year}"
    return f"{day}. {month} {year} klo {hour}:{minute:02d}"


def fetch_all_events(api_url: str, session: requests.Session, max_retries: int = 3) -> List[dict]:
    """Fetch all pages from the API and return a flattened list of events."""
    results: List[dict] = []
    url = api_url
    retries = 0
    while url:
        try:
            logging.debug("Fetching %s", url)
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            page_results = data.get("results", [])
            results.extend(page_results)
            url = data.get("next_url")
            retries = 0
        except requests.RequestException as e:
            retries += 1
            if retries > max_retries:
                logging.error("Failed to fetch %s: %s", url, e)
                raise
            backoff = 2 ** retries
            logging.warning("Error fetching %s: %s. Retrying in %ss...", url, e, backoff)
            time.sleep(backoff)
    logging.info("Fetched %d events", len(results))
    return results


def within_days(event_dt: Optional[datetime.datetime], days: int) -> bool:
    if not event_dt:
        return False
    today = datetime.date.today()
    event_date = event_dt.date()
    delta = (event_date - today).days
    return 0 <= delta <= days


def build_mastodon_client(access_token: Optional[str], base_url: str) -> Optional[Mastodon]:
    if not access_token:
        logging.warning("No Mastodon access token provided; running in dry-run / preview mode")
        return None
    return Mastodon(access_token=access_token, api_base_url=base_url)


def post_to_mastodon(client: Optional[Mastodon], status: str, dry_run: bool = True) -> bool:
    logging.info("Posting to Mastodon: %s", status.replace("\n", " ")[:200])
    if dry_run or client is None:
        logging.info("Dry-run: not actually posting")
        return True
    try:
        client.status_post(status)
        return True
    except MastodonError as e:
        logging.error("Mastodon post failed: %s", e)
        return False

def _check_tags(demo_tags: List[str]) -> List[str]:
    """
    Check the tags from the demo, and if they contain spaces, remove the space and capitalize each word.
    """
    checked_tags = []
    for tag in demo_tags:
        tag = tag.strip()
        if " " in tag:
            continue

        checked_tags.append(tag)
    return checked_tags


def process_events(
    events: Iterable[dict],
    posted: Set[str],
    client: Optional[Mastodon],
    data_file: str,
    dry_run: bool,
    max_days: int,
) -> int:
    posted_count = 0
    session_now = datetime.datetime.now()
    for event in events:
        slug_or_id = event.get("slug") or event.get("_id") or event.get("id")
        if not slug_or_id:
            logging.debug("Skipping event without id/slug: %s", event)
            continue
        link = f"https://mielenosoitukset.fi/demonstration/{slug_or_id}"
        if link in posted:
            logging.debug("Already posted: %s", link)
            continue

        title = event.get("title") or event.get("name") or "Ilman otsikkoa"

        # parse date
        raw_date = event.get("date") or event.get("start_date") or event.get("start_time")
        event_dt = parse_event_date(raw_date) if raw_date else None
        if not within_days(event_dt, max_days):
            logging.debug("Skipping outside window: %s (date=%s)", title, raw_date)
            continue

        formatted = event.get("formatted_date")
        if formatted:
            title_with_date = f"{formatted} — {title}"
        elif event_dt:
            title_with_date = f"{format_finnish_date(event_dt)} — {title}"
        else:
            title_with_date = title

        tags = event.get("tags", [])
        tags = _check_tags(tags)
        if not "mielenosoitus" in tags:
            tags.append("mielenosoitus")
            
        if tags:
            tag_str = " ".join(f"#{tag}" for tag in tags)
            status = f"📣 Uusi mielenosoitus: {title_with_date}\n🔗 {link}\n{tag_str}"
        else:
            status = f"📣 Uusi mielenosoitus: {title_with_date}\n🔗 {link}\n#aktivismi #mielenosoitus"
            
        success = post_to_mastodon(client, status, dry_run=dry_run)
        if success:
            append_posted(data_file, link)
            posted.add(link)
            posted_count += 1
        # be polite
        time.sleep(1)
    logging.info("Posted %d new events", posted_count)
    return posted_count


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Automated Mastodon poster for mielenosoitukset.fi")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="Events API URL")
    parser.add_argument("--mastodon-base", default=DEFAULT_MASTODON_BASE, help="Mastodon instance base URL")
    # Try to load .env for local development; no-op if python-dotenv is not installed
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        load_dotenv = None
    if load_dotenv:
        load_dotenv()

    parser.add_argument(
        "--access-token",
        default=os.getenv("MASTODON_ACCESS_TOKEN"),
        help="Mastodon access token (or set MASTODON_ACCESS_TOKEN in .env or environment)",
    )

    parser.add_argument("--data-file", default=DEFAULT_DATA_FILE, help="File to record posted event links")
    parser.add_argument("--max-days", type=int, default=DEFAULT_MAX_DAYS, help="How many days ahead to post events for")
    parser.add_argument("--interval", type=int, default=DEFAULT_CHECK_INTERVAL, help="Seconds between checks when running continuously")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--dry-run", action="store_true", help="Do not actually post to Mastodon")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    args = parser.parse_args(argv)


    setup_logging(args.log_level)
    
    # lets add the max_days to the api url if not already present
    if "max_days_till=" not in args.api_url:
        separator = "&" if "?" in args.api_url else "?"
        args.api_url = f"{args.api_url}{separator}max_days_till={args.max_days}"

    logging.info("Starting mastobot: api=%s max_days=%s dry_run=%s", args.api_url, args.max_days, args.dry_run)

    posted = load_posted(args.data_file)
    client = build_mastodon_client(args.access_token, args.mastodon_base)

    session = requests.Session()
    exit_code = 0
    try:
        while True:
            try:
                events = fetch_all_events(args.api_url, session)
                process_events(events, posted, client, args.data_file, args.dry_run or client is None, args.max_days)
            except Exception as e:
                logging.exception("Error while fetching or processing events: %s", e)
            if args.once:
                break
            logging.info("Sleeping %s seconds...", args.interval)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        logging.info("Interrupted by user")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
