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
import html
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Tuple

import requests
from mastodon import Mastodon, MastodonError
from bson import ObjectId

from mielenosoitukset_fi.database_manager import DatabaseManager

mongo = DatabaseManager().get_instance().get_db()

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
DEFAULT_CHECK_INTERVAL = int(os.getenv("MO_CHECK_INTERVAL", "60"))

subscriptions_collection = mongo["mastobot_subscriptions"]
mastobot_meta_collection = mongo["mastobot_meta"]
INSTRUCTIONS_COMMENT = (
    "💡 Haluatko muistutuksen mielenosoituksesta? Vastaa tähän ketjuun kirjoittamalla `!subscribeme` "
    "niin saat Mastodon-viestit 7 päivää ja 24 tuntia ennen tapahtumaa sekä tiedon peruutuksista."
)


@dataclass
class PostedState:
    links: Set[str] = field(default_factory=set)
    announcements: Dict[str, dict] = field(default_factory=dict)
    cancellations: Set[str] = field(default_factory=set)
    status_to_demo: Dict[str, str] = field(default_factory=dict)


def _extract_demo_id_from_link(link: Optional[str]) -> Optional[str]:
    if not link or "/demonstration/" not in link:
        return None
    tail = link.split("/demonstration/", 1)[1]
    tail = tail.split("?", 1)[0]
    return tail.split("/", 1)[0]


def load_posted_state() -> PostedState:
    state = PostedState()
    for doc in mongo.posted_events.find({}):
        link = doc.get("link")
        if link:
            state.links.add(link)
        for alias in doc.get("link_aliases", []):
            if alias:
                state.links.add(alias)
        demo_id = str(doc.get("demo_id") or _extract_demo_id_from_link(link) or "")
        post_type = doc.get("post_type", "announcement")
        status_id = doc.get("status_id")
        if post_type == "announcement" and demo_id:
            state.announcements[demo_id] = {
                "link": link,
                "status_id": str(status_id) if status_id else None,
                "posted_at": doc.get("created_at"),
            }
            if status_id:
                state.status_to_demo[str(status_id)] = demo_id
        elif post_type == "cancellation" and demo_id:
            state.cancellations.add(demo_id)
    return state

def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )




def append_posted(
    link: str,
    state: PostedState,
    *,
    demo_id: Optional[str] = None,
    status_id: Optional[str] = None,
    post_type: str = "announcement",
    slug: Optional[str] = None,
    link_aliases: Optional[List[str]] = None,
) -> None:
    doc = {
        "link": link,
        "post_type": post_type,
        "created_at": datetime.datetime.utcnow(),
    }
    if demo_id:
        doc["demo_id"] = demo_id
    if status_id:
        doc["status_id"] = status_id
    if slug:
        doc["slug"] = slug
    if link_aliases:
        doc["link_aliases"] = link_aliases
    mongo.posted_events.insert_one(doc)

    state.links.add(link)
    if link_aliases:
        for alias in link_aliases:
            state.links.add(alias)
    if demo_id and post_type == "announcement":
        state.announcements[demo_id] = {
            "link": link,
            "status_id": status_id,
            "posted_at": doc["created_at"],
        }
        if status_id:
            state.status_to_demo[str(status_id)] = demo_id
    elif demo_id and post_type == "cancellation":
        state.cancellations.add(demo_id)


def post_instructions_comment(
    client: Optional[Mastodon],
    base_status_id: Optional[str],
    dry_run: bool,
) -> None:
    """Reply under the published status with instructions for !subscribeme usage."""
    if not base_status_id:
        return
    post_to_mastodon(
        client,
        INSTRUCTIONS_COMMENT,
        dry_run=dry_run,
        in_reply_to_id=base_status_id,
    )


def build_event_link(demo_id: str) -> str:
    return f"https://mielenosoitukset.fi/demonstration/{demo_id}"


def build_link_variants(primary_id: Optional[str], slug: Optional[str]) -> List[str]:
    variants: List[str] = []
    seen: Set[str] = set()

    def _add(identifier: Optional[str]):
        if not identifier:
            return
        identifier = str(identifier)
        link = build_event_link(identifier)
        if link not in seen:
            seen.add(link)
            variants.append(link)

    _add(primary_id)
    if slug and slug != primary_id:
        _add(slug)
    return variants


def format_city_line(city: Optional[str]) -> str:
    if not city:
        return ""
    clean = city.strip()
    return f"📍 {clean.capitalize()}" if clean else ""


def _is_city_in_tags(tags: List[str], city: str) -> bool:
    lowered = [tag.lower() for tag in tags]
    return city.lower() in lowered


def build_tag_string(
    demo_tags: List[str],
    city: Optional[str],
    extra_tags: Optional[List[str]] = None,
) -> str:
    tags = _check_tags(demo_tags or [])
    if "mielenosoitus" not in tags:
        tags.append("mielenosoitus")
    if city:
        city_clean = city.strip()
        if city_clean and not _is_city_in_tags(tags, city_clean):
            tags.append(city_clean)
            tags.append(f"miekkarit_{city_clean.lower()}")
    if extra_tags:
        for tag in extra_tags:
            if tag and tag not in tags:
                tags.append(tag)
    return " ".join(f"#{tag}" for tag in tags)


def format_time_window(event: dict) -> str:
    start_time = event.get("start_time")
    end_time = event.get("end_time")
    if start_time and end_time:
        return f"{start_time} – {end_time}"
    if start_time:
        return f"alkaen {start_time}"
    return ""


def index_events_by_id(events: Iterable[dict]) -> Dict[str, dict]:
    indexed: Dict[str, dict] = {}
    for event in events:
        demo_id = event.get("_id") or event.get("id")
        if demo_id:
            indexed[str(demo_id)] = event
    return indexed


def fetch_demo_by_identifier(demo_id: str) -> Optional[dict]:
    """
    Fetch a demonstration document directly from Mongo using various identifiers.
    Allows Mastobot to find demos that are no longer present in the public API listing.
    """
    if not demo_id:
        return None

    queries = []
    try:
        queries.append({"_id": ObjectId(demo_id)})
    except Exception:
        pass
    queries.append({"slug": demo_id})
    queries.append({"running_number": demo_id})

    for query in queries:
        demo = mongo.demonstrations.find_one(query)
        if demo:
            if isinstance(demo.get("_id"), ObjectId):
                demo["_id"] = str(demo["_id"])
            return demo
    return None


def strip_html_tags(text: str) -> str:
    clean = re.sub(r"<[^>]+>", "", text or "")
    return html.unescape(clean).strip()


def extract_demo_id_from_status(status: dict) -> Optional[str]:
    if not status:
        return None
    content = status.get("content") or ""
    match = re.search(r"/demonstration/([A-Za-z0-9_-]+)", content)
    if match:
        return match.group(1)
    urls = status.get("mentions") or []
    for mention in urls:
        acct = mention.get("acct")
        if acct and "/demonstration/" in acct:
            maybe = acct.split("/demonstration/", 1)[1]
            return maybe.split("?", 1)[0]
    return None


def resolve_demo_from_status(
    client: Optional[Mastodon],
    status: dict,
    posted_state: PostedState,
) -> Tuple[Optional[str], Optional[str]]:
    if not status:
        return None, None
    queue = [status]
    visited = set()
    while queue:
        current = queue.pop(0)
        if not current:
            continue
        status_id = str(current.get("id") or "")
        if status_id in posted_state.status_to_demo:
            return posted_state.status_to_demo[status_id], status_id
        demo_id = extract_demo_id_from_status(current)
        if demo_id and demo_id in posted_state.announcements:
            return demo_id, status_id or None
        parent_id = current.get("in_reply_to_id")
        if not parent_id or parent_id in visited or client is None:
            continue
        visited.add(parent_id)
        try:
            parent_status = client.status(parent_id)
        except MastodonError:
            break
        queue.append(parent_status)
    return None, None


def get_meta(key: str, default: Optional[str] = None) -> Optional[str]:
    doc = mastobot_meta_collection.find_one({"_id": key})
    if not doc:
        return default
    return doc.get("value", default)


def set_meta(key: str, value: str) -> None:
    mastobot_meta_collection.update_one(
        {"_id": key}, {"$set": {"value": value, "updated_at": datetime.datetime.utcnow()}}, upsert=True
    )


def parse_event_datetime(event: dict) -> Optional[datetime.datetime]:
    date_str = event.get("date")
    if not date_str:
        return None
    try:
        date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None
    start_time = (event.get("start_time") or "12:00").strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            time_obj = datetime.datetime.strptime(start_time, fmt).time()
            return datetime.datetime.combine(date_obj, time_obj)
        except ValueError:
            continue
    return datetime.datetime.combine(date_obj, datetime.time(12, 0))


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


def post_to_mastodon(
    client: Optional[Mastodon],
    status: str,
    dry_run: bool = True,
    visibility: str = "public",
    in_reply_to_id: Optional[str] = None,
) -> Tuple[bool, Optional[dict]]:
    logging.info("Posting to Mastodon: %s", status.replace("\n", " ")[:200])
    if dry_run or client is None:
        logging.info("Dry-run: not actually posting")
        return True, None
    try:
        result = client.status_post(status, visibility=visibility, in_reply_to_id=in_reply_to_id)
        return True, result
    except MastodonError as e:
        logging.error("Mastodon post failed: %s", e)
        return False, None

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
    posted_state: PostedState,
    client: Optional[Mastodon],
    dry_run: bool,
    max_days: int,
) -> int:
    posted_count = 0
    for event in events:
        slug_or_id = event.get("_id") or event.get("id")
        slug_value = event.get("slug")
        if not slug_or_id and not slug_value:
            logging.debug("Skipping event without id/slug: %s", event)
            continue
        primary_id = str(slug_or_id or slug_value)
        link_variants = build_link_variants(primary_id, slug_value)
        already_posted = any(link in posted_state.links for link in link_variants)
        if already_posted:
            logging.debug("Already posted: %s", primary_id)
            continue
        link = build_event_link(slug_value or primary_id)

        title = event.get("title") or event.get("name")
        if not title:
            logging.debug("Skipping event without title: %s", event)
            continue

        date_str = event.get("formatted_date") or event.get("date") or ""
        time_str = format_time_window(event)
        city_line = format_city_line(event.get("city"))

        event_dt = parse_event_date(event.get("date")) if event.get("date") else None
        if not within_days(event_dt, max_days):
            logging.debug("Skipping outside window: %s (date=%s)", title, date_str)
            continue

        tag_str = build_tag_string(event.get("tags", []), event.get("city"))

        lines = [title, f"{date_str} {time_str}".strip(), city_line, link, tag_str]
        status = "\n".join([line for line in lines if line])

        success, status_payload = post_to_mastodon(client, status, dry_run=dry_run)
        if success:
            status_id = str(status_payload["id"]) if status_payload else None
            append_posted(
                link,
                posted_state,
                demo_id=primary_id,
                status_id=status_id,
                post_type="announcement",
                slug=slug_value,
                link_aliases=link_variants,
            )
            post_instructions_comment(client, status_id, dry_run)
            posted_count += 1
            time.sleep(1)
    logging.info("Posted %d new events", posted_count)
    return posted_count


def handle_cancellations(
    events: Iterable[dict],
    posted_state: PostedState,
    client: Optional[Mastodon],
    dry_run: bool,
) -> int:
    cancelled_posts = 0
    for event in events:
        if not event.get("cancelled"):
            continue
        demo_id_value = event.get("_id") or event.get("id")
        slug_value = event.get("slug")
        if not demo_id_value and not slug_value:
            continue
        demo_id = str(demo_id_value or slug_value)
        link_variants = build_link_variants(demo_id, slug_value)
        if demo_id in posted_state.cancellations:
            continue
        if demo_id not in posted_state.announcements:
            continue

        title = event.get("title") or event.get("name") or "Mielenosoitus"
        date_str = event.get("formatted_date") or event.get("date") or ""
        time_str = format_time_window(event)
        city_line = format_city_line(event.get("city"))
        tag_str = build_tag_string(event.get("tags", []), event.get("city"), extra_tags=["peruttu"])
        link = build_event_link(demo_id)

        status_lines = [
            f"❌ Peruttu: {title}",
            f"{date_str} {time_str}".strip(),
            city_line,
            f"Tämä mielenosoitus on peruttu. Lisätiedot: {link}",
            tag_str,
        ]
        status = "\n".join([line for line in status_lines if line])
        in_reply_to = posted_state.announcements.get(demo_id, {}).get("status_id")

        success, payload = post_to_mastodon(
            client,
            status,
            dry_run=dry_run,
            in_reply_to_id=in_reply_to,
        )
        if success:
            status_id = str(payload["id"]) if payload else None
            append_posted(
                link,
                posted_state,
                demo_id=demo_id,
                status_id=status_id,
                post_type="cancellation",
                slug=slug_value,
                link_aliases=link_variants,
            )
            post_instructions_comment(client, status_id, dry_run)
            cancelled_posts += 1
            time.sleep(1)

    if cancelled_posts:
        logging.info("Posted %d cancellation updates", cancelled_posts)
    return cancelled_posts


def subscribe_account(
    client: Optional[Mastodon],
    account: dict,
    demo_id: str,
    request_status: dict,
    events_by_id: Dict[str, dict],
    dry_run: bool,
) -> None:
    acct = account.get("acct")
    if not acct:
        return
    account_id = account.get("id")
    if account_id is None:
        logging.warning("Subscription request missing account id; skipping")
        return
    demo = events_by_id.get(str(demo_id))
    if not demo:
        # Fall back to querying Mongo directly for older/archived demonstrations
        demo = fetch_demo_by_identifier(str(demo_id))
        if demo and not demo.get("formatted_date"):
            parsed_dt = parse_event_date(demo.get("date"))
            if parsed_dt:
                demo["formatted_date"] = format_finnish_date(parsed_dt)
    if not demo:
        message = f"@{acct} En löytänyt mielenosoitusta tietokannasta – yritä hetken kuluttua uudelleen."
        post_to_mastodon(
            client,
            message,
            dry_run=dry_run,
            visibility="direct",
            in_reply_to_id=str(request_status.get("id")),
        )
        return

    title = demo.get("title") or demo.get("name") or "Mielenosoitus"
    date_text = demo.get("formatted_date") or demo.get("date") or ""
    link = build_event_link(str(demo_id))
    request_status_id = request_status.get("id")
    account_id_str = str(account_id)
    existing = subscriptions_collection.find_one(
        {"demo_id": str(demo_id), "account_id": account_id_str}
    )

    if existing:
        response = f"@{acct} Olet jo tilannut muistutukset tapahtumaan \"{title}\"."
        doc_id = existing["_id"]
    else:
        doc = {
            "demo_id": str(demo_id),
            "account_id": account_id_str,
            "acct": acct,
            "display_name": account.get("display_name"),
            "username": account.get("username"),
            "created_at": datetime.datetime.utcnow(),
            "source_status_id": str(request_status_id) if request_status_id else None,
            "thread_id": None,
            "notifications": {
                "week_before": None,
                "day_before": None,
                "cancelled": None,
            },
            "link": link,
            "title_snapshot": title,
            "date_snapshot": date_text,
        }
        result = subscriptions_collection.insert_one(doc)
        doc_id = result.inserted_id
        response = (
            f"@{acct} Tilasit muistutukset tapahtumaan \"{title}\" ({date_text}). "
            "Saat viestit 7 päivää, 24 tuntia ja mahdollisesta peruutuksesta."
        )

    in_reply_to = str(request_status_id) if request_status_id else None

    success, payload = post_to_mastodon(
        client,
        response,
        dry_run=dry_run,
        visibility="direct",
        in_reply_to_id=in_reply_to,
    )
    thread_id = str(payload["id"]) if payload else None
    if not thread_id:
        thread_id = in_reply_to
    subscriptions_collection.update_one({"_id": doc_id}, {"$set": {"thread_id": thread_id}})


def process_mentions(
    client: Optional[Mastodon],
    posted_state: PostedState,
    events_by_id: Dict[str, dict],
    dry_run: bool,
) -> None:
    if client is None:
        return
    last_id = get_meta("last_notification_id")
    try:
        if last_id:
            notifications = client.notifications(since_id=last_id, types=["mention"])
        else:
            notifications = client.notifications(limit=30, types=["mention"])
    except MastodonError as exc:
        logging.error("Failed to fetch notifications: %s", exc)
        return

    notifications = list(notifications)
    if not notifications:
        return

    notifications.sort(key=lambda n: int(n["id"]))
    max_id = int(last_id) if last_id else 0
    latest_id = last_id

    for note in notifications:
        note_id = note.get("id")
        if note_id:
            try:
                note_id_int = int(note_id)
                if note_id_int > max_id:
                    max_id = note_id_int
                    latest_id = str(note_id)
            except (TypeError, ValueError):
                pass

        if note.get("type") != "mention":
            continue
        status = note.get("status") or {}
        content = strip_html_tags(status.get("content", ""))
        if "!subscribeme" not in content.lower():
            continue

        account = note.get("account") or {}
        demo_id, _ = resolve_demo_from_status(client, status, posted_state)
        if not demo_id:
            acct = account.get("acct")
            if not acct:
                continue
            message = (
                f"@{acct} En löytänyt liittyvää mielenosoitusta. "
                "Varmista, että vastaat suoraan tapahtumapostaukseen."
            )
            post_to_mastodon(
                client,
                message,
                dry_run=dry_run,
                visibility="direct",
                in_reply_to_id=str(status.get("id")),
            )
            continue

        subscribe_account(client, account, demo_id, status, events_by_id, dry_run)

    if latest_id:
        set_meta("last_notification_id", latest_id)


def notify_subscription_stage(
    subscription: dict,
    demo: dict,
    stage: str,
    client: Optional[Mastodon],
    dry_run: bool,
) -> bool:
    acct = subscription.get("acct")
    if not acct:
        return False
    stage_label = "7 päivän" if stage == "week_before" else "24 tunnin"
    title = demo.get("title") or demo.get("name") or "Mielenosoitus"
    date_str = demo.get("formatted_date") or demo.get("date") or ""
    time_str = format_time_window(demo)
    city_line = format_city_line(demo.get("city"))
    link = build_event_link(str(demo.get("_id") or demo.get("id")))
    message_lines = [
        f"@{acct} {stage_label} muistutus: \"{title}\"",
        f"{date_str} {time_str}".strip(),
        city_line,
        f"Lisätiedot: {link}",
    ]
    status = "\n".join([line for line in message_lines if line])
    in_reply_to = subscription.get("thread_id") or subscription.get("source_status_id")

    success, payload = post_to_mastodon(
        client,
        status,
        dry_run=dry_run,
        visibility="direct",
        in_reply_to_id=in_reply_to,
    )
    if success:
        update = {
            f"notifications.{stage}": datetime.datetime.utcnow(),
            "updated_at": datetime.datetime.utcnow(),
        }
        if not subscription.get("thread_id") and payload:
            update["thread_id"] = str(payload["id"])
        subscriptions_collection.update_one({"_id": subscription["_id"]}, {"$set": update})
    return success


def notify_subscription_cancellation(
    subscription: dict,
    demo: dict,
    client: Optional[Mastodon],
    dry_run: bool,
) -> None:
    acct = subscription.get("acct")
    if not acct:
        return
    title = demo.get("title") or demo.get("name") or "Mielenosoitus"
    link = build_event_link(str(demo.get("_id") or demo.get("id")))
    message = (
        f"@{acct} Tapahtuma \"{title}\" on peruttu. "
        f"Lue viimeisimmät tiedot: {link}"
    )
    in_reply_to = subscription.get("thread_id") or subscription.get("source_status_id")
    success, payload = post_to_mastodon(
        client,
        message,
        dry_run=dry_run,
        visibility="direct",
        in_reply_to_id=in_reply_to,
    )
    if success:
        update = {
            "notifications.cancelled": datetime.datetime.utcnow(),
            "updated_at": datetime.datetime.utcnow(),
        }
        if not subscription.get("thread_id") and payload:
            update["thread_id"] = str(payload["id"])
        subscriptions_collection.update_one({"_id": subscription["_id"]}, {"$set": update})


def process_subscription_reminders(
    client: Optional[Mastodon],
    events_by_id: Dict[str, dict],
    dry_run: bool,
) -> None:
    if client is None:
        return
    now = datetime.datetime.utcnow()
    for subscription in subscriptions_collection.find({}):
        demo_id = str(subscription.get("demo_id"))
        if not demo_id:
            continue
        demo = events_by_id.get(demo_id)
        if not demo:
            continue
        notifications = subscription.get("notifications") or {}

        if demo.get("cancelled"):
            if not notifications.get("cancelled"):
                notify_subscription_cancellation(subscription, demo, client, dry_run)
            continue

        event_dt = parse_event_datetime(demo)
        if not event_dt:
            continue

        week_target = event_dt - datetime.timedelta(days=7)
        day_target = event_dt - datetime.timedelta(days=1)

        if now >= week_target and not notifications.get("week_before"):
            notify_subscription_stage(subscription, demo, "week_before", client, dry_run)

        if now >= day_target and not notifications.get("day_before"):
            notify_subscription_stage(subscription, demo, "day_before", client, dry_run)

        if now >= event_dt:
            subscriptions_collection.update_one(
                {"_id": subscription["_id"]},
                {"$set": {"status": "completed", "completed_at": now}},
            )

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
    if "include_cancelled=" not in args.api_url:
        separator = "&" if "?" in args.api_url else "?"
        args.api_url = f"{args.api_url}{separator}include_cancelled=true"

    logging.info("Starting mastobot: api=%s max_days=%s dry_run=%s", args.api_url, args.max_days, args.dry_run)

    posted_state = load_posted_state()
    client = build_mastodon_client(args.access_token, args.mastodon_base)

    session = requests.Session()
    exit_code = 0
    try:
        while True:
            try:
                events = fetch_all_events(args.api_url, session)
                events_by_id = index_events_by_id(events)
                dry_mode = args.dry_run or client is None
                process_events(events, posted_state, client, dry_mode, args.max_days)
                handle_cancellations(events, posted_state, client, dry_mode)
                if client and not args.dry_run:
                    process_mentions(client, posted_state, events_by_id, dry_mode)
                    process_subscription_reminders(client, events_by_id, dry_mode)
                else:
                    logging.debug("Skipping mention/subscription processing (dry-run or no client)")
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
