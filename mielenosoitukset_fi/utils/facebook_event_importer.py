"""Facebook event import via the Apify ``apify~facebook-events-scraper`` actor.

The public submission form lets users paste a link to a public Facebook event
and prefills the demonstration form from the scraped event data. All Apify
calls, response parsing, sanitization, and date/time conversion live in this
module so the route stays thin and the behavior is testable.

Everything returned from Apify is treated as untrusted input:
- text fields are passed through the same HTML sanitizer used for submitted
  descriptions (allowlisted tags, http/https/mailto links only),
- the city is only accepted if it matches a known Finnish municipality,
- dates/times are re-parsed and normalized to the site's ISO formats,
- strings have a length cap.

The importer never blocks submission and never talks to moderation: it only
produces a prefill payload plus warnings for the user to review.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests

from config import Config
from mielenosoitukset_fi.utils.cities import CITY_KEY_TO_NAME, normalize_city_key
from mielenosoitukset_fi.utils.content_formatting import (
    html_to_markdown,
    markdown_to_html,
)

logger = logging.getLogger(__name__)

# Facebook event URLs we accept (www/mobile/mbasic/web subdomains). The event
# id is a plain number; query strings and trailing paths are allowed.
EVENT_URL_RE = re.compile(
    r"^https?://(?:[a-z0-9-]+\.)*facebook\.com/events/(\d+)(?:[/?].*)?$",
    re.IGNORECASE,
)

# Hard caps so a single scraper response can never blow up the page or DB.
MAX_TITLE_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 50_000
MAX_ADDRESS_LENGTH = 300
MAX_ORGANIZER_LENGTH = 200
MAX_IMAGE_BYTES = 15_000_000

# Keys shown in the field summary. End date/time is optional in the form, so
# it is reported as "imported" when present but never as "missing".
_NOTE_FIELDS = ("end_date", "end_time", "image_url")
_FIELD_KEYS = (
    "title",
    "description_html",
    "start_date",
    "start_time",
    "end_date",
    "end_time",
    "city",
    "address",
    "organizer",
    "facebook_url",
    "image_url",
)


class FacebookImportError(Exception):
    """Raised when an event cannot be imported.

    ``code`` is a stable machine-readable key the route maps to a localized,
    user-safe message. ``status_code`` is the HTTP status used for the AJAX
    response.
    """

    def __init__(self, code: str, status_code: int = 500):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass
class ImportedFacebookEvent:
    """Normalized, sanitized event data ready for the submission form."""

    title: str = ""
    description_html: str = ""
    start_date: str = ""
    start_time: str = ""
    end_date: str = ""
    end_time: str = ""
    city: str = ""
    address: str = ""
    organizer: str = ""
    organizers: List[str] = field(default_factory=list)
    facebook_url: str = ""
    image_url: str = ""

    # Field keys that were filled (machine keys, order preserved).
    imported: List[str] = field(default_factory=list)
    # Field keys that could not be filled and should be completed manually.
    missing: List[str] = field(default_factory=list)
    # Machine keys for warnings (e.g. "canceled", "past").
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "description_html": self.description_html,
            "start_date": self.start_date,
            "start_time": self.start_time,
            "end_date": self.end_date,
            "end_time": self.end_time,
            "city": self.city,
            "address": self.address,
            "organizer": self.organizer,
            "facebook_url": self.facebook_url,
            "image_url": self.image_url,
            "imported": self.imported,
            "missing": self.missing,
            "warnings": self.warnings,
        }


def parse_event_url(raw_url: str) -> str:
    """Normalize a pasted Facebook event link into a canonical URL.

    Accepts links with or without a scheme and m.www/mbasic/web subdomains.
    Raises :class:`FacebookImportError` (code ``invalid_url``) when no event
    id can be extracted.
    """
    raw = (raw_url or "").strip()
    if not raw:
        raise FacebookImportError("missing_url", status_code=400)
    if not re.match(r"^https?://", raw, re.IGNORECASE):
        raw = "https://" + raw

    match = EVENT_URL_RE.match(raw)
    if not match:
        raise FacebookImportError("invalid_url", status_code=400)

    return f"https://www.facebook.com/events/{match.group(1)}/"


class FacebookEventImporter:
    """Imports a public Facebook event and normalizes it for the form."""

    def import_event(self, raw_url: str) -> ImportedFacebookEvent:
        """Fetch and normalize the event behind ``raw_url``."""
        canonical_url = parse_event_url(raw_url)
        item = self._fetch_event(canonical_url)
        return self._normalize_event(item, canonical_url)

    # -- Apify ---------------------------------------------------------------

    def _fetch_event(self, url: str) -> Dict[str, Any]:
        token = getattr(Config, "APIFY_API_TOKEN", "") or ""
        if not token:
            raise FacebookImportError("not_configured", status_code=503)

        base_url = getattr(Config, "APIFY_API_BASE_URL", "https://api.apify.com/v2")
        actor_id = str(
            getattr(
                Config, "APIFY_FACEBOOK_ACTOR_ID", "apify~facebook-events-scraper"
            )
            or "apify~facebook-events-scraper"
        ).strip()
        # Apify actor ids use the "owner~name" form; tolerate the historical
        # "owner/name" spelling so existing configs keep working.
        if "/" in actor_id:
            actor_id = actor_id.replace("/", "~")
        sync_timeout = int(
            getattr(Config, "APIFY_SYNC_TIMEOUT_SECONDS", 120) or 120
        )

        endpoint = (
            f"{base_url}/acts/{actor_id}/run-sync-get-dataset-items?timeout={sync_timeout}"
            "&maxItems=1&limit=1&format=json"
        )
        payload = {"startUrls": [url], "maxEvents": 30}
        headers = {"Authorization": f"Bearer {token}"}

        try:
            response = requests.post(
                endpoint, json=payload, headers=headers, timeout=sync_timeout + 10
            )
        except requests.RequestException as exc:
            logger.warning("Apify fetch failed for %r: %s", url, exc)
            raise FacebookImportError("apify_network", status_code=502) from exc

        if response.status_code in (401, 403):
            logger.error("Apify rejected credentials (HTTP %s).", response.status_code)
            raise FacebookImportError("apify_auth", status_code=503)
        if response.status_code == 402:
            logger.error("Apify reported the user has no credits in the factor.")
            raise FacebookImportError("apify_payment", status_code=503)
        if response.status_code == 429:
            logger.warning("Apify rate limited during Facebook import.")
            raise FacebookImportError("apify_rate_limit", status_code=429)
        if response.status_code == 404:
            logger.warning("Apify actor not found (HTTP 404).")
            raise FacebookImportError("apify_unavailable", status_code=502)
        if response.status_code == 408:
            raise FacebookImportError("apify_timeout", status_code=504)
        if response.status_code >= 400:
            logger.warning(
                "Apify returned HTTP %s during Facebook import.",
                response.status_code,
            )
            raise FacebookImportError("apify_failed", status_code=502)

        try:
            items = response.json()
        except ValueError as exc:
            logger.warning("Apify returned non-JSON response: %s", exc)
            raise FacebookImportError("unexpected_response", status_code=502) from exc

        if not isinstance(items, list):
            logger.warning("Apify returned a non-list response for %r", url)
            raise FacebookImportError("unexpected_response", status_code=502)
        if not items:
            logger.info("Apify returned no events for %r", url)
            raise FacebookImportError("empty_result", status_code=404)

        item = items[0]
        if not isinstance(item, dict):
            logger.warning("Apify returned a non-dict first item for %r", url)
            raise FacebookImportError("unexpected_response", status_code=502)
        return item

    # -- Normalization -------------------------------------------------------

    def _normalize_event(
        self, item: Dict[str, Any], canonical_url: str
    ) -> ImportedFacebookEvent:
        event = ImportedFacebookEvent()
        event.facebook_url = canonical_url

        title = item.get("name") or ""
        if not isinstance(title, str):
            title = str(title)
        fields = {
            "title": title.strip()[:MAX_TITLE_LENGTH],
            "address": _location_address(item),
            "start_date": None,
            "start_time": None,
        }

        # Determine organizer(s) from the item.
        event.organizers = _organizer_names(item)
        event.organizer = event.organizers[0] if event.organizers else _first_organizer(item)

        # Date/time come from the ISO start stamp in UTC.
        start = _to_local_datetime(item.get("utcStartDate"))
        if start:
            fields["start_date"], fields["start_time"] = _split_datetime(start)
        else:
            # Defensive fallback to the actor's display-only startTime.
            time_part = _parse_time_text(item.get("startTime"))
            if time_part:
                fields["start_time"] = time_part
                event.warnings.append("approximate_time")

        description = _sanitize_description(item.get("description"))
        city = _find_matching_city(_location_city(item))

        for key in ("title", "description_html", "city", "address"):
            setattr(event, key, fields.get(key) or "")

        description_html = ""
        if description:
            description_html = description
        event.description_html = description_html

        event.start_date = (fields.get("start_date") or "").strip()
        event.start_time = (fields.get("start_time") or "").strip()

        # End date/time are optional; copy them when the actor provides them
        # (future-proofing) but never nag about them in the "missing" list.
        end = _to_local_datetime(item.get("utcEndDate"))
        if end:
            event.end_date, event.end_time = _split_datetime(end)

        if not event.city:
            # The street address may contain a "street, City" suffix that we
            # can use — but only when it resolves to a known municipality.
            event.city = _find_matching_city(_city_from_address(event.address))
        if event.city:
            event.address = _strip_city_suffix(event.address, event.city)

        if item.get("isCanceled"):
            event.warnings.append("canceled")
        if item.get("isPast"):
            event.warnings.append("past")
        if str(item.get("eventType", "")).upper() != "PUBLIC":
            event.warnings.append("not_public")
        if item.get("isOnline"):
            event.warnings.append("online")

        # Best‑effort: download and upload the event's cover photo to S3.
        _attach_cover_image(item, event)

        event.imported, event.missing = _field_summary(event)
        return event


def _to_local_datetime(value: Any) -> Optional[datetime]:
    """Parse an ISO timestamp with a trailing ``Z`` and convert to local time."""
    if not value:
        return None
    try:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    try:
        tz = ZoneInfo(Config.DEFAULT_TIMEZONE)
    except Exception:
        tz = timezone.utc
    return parsed.astimezone(tz)


def _split_datetime(value: datetime):
    return value.strftime("%Y-%m-%d"), value.strftime("%H:%M")


def _parse_time_text(value: Any) -> str:
    """Best-effort parse of the actor's display-only ``startTime`` value."""
    if not value:
        return ""
    text = str(value).strip()
    match = re.match(r"^(\d{1,2}):(\d{2})\s*(AM|PM)?$", text, re.IGNORECASE)
    if not match:
        return ""
    hour = int(match.group(1))
    minute = int(match.group(2))
    if minute > 59:
        return ""
    suffix = (match.group(3) or "").upper()
    if suffix == "PM" and hour < 12:
        hour += 12
    elif suffix == "AM" and hour == 12:
        hour = 0
    if hour > 23:
        return ""
    return f"{hour:02d}:{minute:02d}"


def _first_organizer(item: Dict[str, Any]) -> str:
    organizators = item.get("organizators") or []
    if isinstance(organizators, list) and organizators:
        first = organizators[0]
        if isinstance(first, dict):
            name = first.get("name")
            if name and str(name).strip():
                return str(name).strip()[:MAX_ORGANIZER_LENGTH]
    name = item.get("organizerCompany")
    if name and str(name).strip():
        return str(name).strip()[:MAX_ORGANIZER_LENGTH]
    return ""


def _location_city(item: Dict[str, Any]) -> str:
    location = item.get("location")
    if isinstance(location, dict):
        city = location.get("city")
        if city and str(city).strip():
            return str(city).strip()
    return ""


def _location_address(item: Dict[str, Any]) -> str:
    location = item.get("location")
    if isinstance(location, dict):
        for key in ("streetAddress", "name", "venue"):
            value = location.get(key)
            if value and str(value).strip():
                return str(value).strip()[:MAX_ADDRESS_LENGTH]
    address = item.get("address")
    if address and str(address).strip():
        return str(address).strip()[:MAX_ADDRESS_LENGTH]
    return ""


def _find_matching_city(raw_city: str) -> str:
    """Resolve a (possibly compound) FB city string to a Finnish municipality."""
    candidate = (raw_city or "").strip().strip(",").strip()
    if not candidate:
        return ""
    # Try progressively shorter prefixes on commas: "Helsinki, Finland" -> "Helsinki".
    parts = [part.strip() for part in candidate.split(",")]
    for width in range(len(parts), 0, -1):
        joined = ", ".join(parts[:width])
        key = normalize_city_key(joined)
        if key in CITY_KEY_TO_NAME:
            return CITY_KEY_TO_NAME[key]
    return ""


def _city_from_address(address: str) -> str:
    """Best-effort guess of a city from the last comma segment of an address."""
    if not address:
        return ""
    parts = [part.strip() for part in address.split(",") if part.strip()]
    if not parts:
        return ""
    return parts[-1]


def _strip_city_suffix(address: str, city: str) -> str:
    """Remove a trailing ", <city>" suffix the importer already filled in a
    separate field so the address is not duplicated."""
    if not address or not city:
        return address
    parts = [part.strip() for part in address.split(",") if part.strip()]
    if not parts:
        return address
    tail = parts[-1]
    if normalize_city_key(tail) == normalize_city_key(city):
        parts = parts[:-1]
    return ", ".join(parts)[:MAX_ADDRESS_LENGTH]


def _sanitize_description(value: Any) -> str:
    """Convert raw description text to safe HTML (allowlisted tags/links)."""
    text = (value or "").strip()
    if not text:
        return ""
    # Script/style blocks and inline event handlers are not content; drop them
    # before the markdown round-trip so nothing like "<script>..." survives.
    text = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1\s*>", " ", text)
    text = re.sub(
        r'(?is)\son\w+\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)', " ", text
    )
    # Pass through the same pipeline used for user-submitted Markdown so only
    # allowlisted HTML ever reaches the Quill editor.
    return markdown_to_html(html_to_markdown(text))


def _field_summary(event: ImportedFacebookEvent):
    imported = [key for key in _FIELD_KEYS if getattr(event, key)]
    missing = [
        key
        for key in _FIELD_KEYS
        if key not in _NOTE_FIELDS and not getattr(event, key)
    ]
    return imported, missing


def _cover_image_url(item: Dict[str, Any]) -> str:
    """Extract the cover photo URL from a Facebook event Apify item."""
    # Primary: actor's imageUrl field
    for key in ("imageUrl", "image_url", "cover"):
        v = item.get(key)
        if isinstance(v, str) and v.strip().startswith("https://"):
            return v.strip()
    # Fallback: coverPhoto array
    cover_photo = item.get("coverPhoto")
    if isinstance(cover_photo, list) and cover_photo:
        first = cover_photo[0]
        if isinstance(first, dict):
            u = first.get("sourceUrl") or first.get("url")
            if isinstance(u, str) and u.strip().startswith("https://"):
                return u.strip()
    # Fallback: picture object
    picture = item.get("picture")
    if isinstance(picture, dict):
        u = picture.get("sourceUrl") or picture.get("url")
        if isinstance(u, str) and u.strip().startswith("https://"):
            return u.strip()
    return ""


def _organizer_names(item: Dict[str, Any]) -> List[str]:
    """Extract all organizer names from a Facebook event Apify item."""
    names: List[str] = []
    organizators = item.get("organizators")
    if isinstance(organizators, list):
        for org in organizators:
            if isinstance(org, dict):
                n = org.get("name")
                if n and str(n).strip():
                    names.append(str(n).strip()[:MAX_ORGANIZER_LENGTH])
    # Fallback to organizerCompany if no organizators
    if not names:
        company = item.get("organizerCompany")
        if company and str(company).strip():
            names.append(str(company).strip()[:MAX_ORGANIZER_LENGTH])
    return names


def _attach_cover_image(
    item: Dict[str, Any], event: ImportedFacebookEvent
) -> None:
    """Best‑effort download and upload the event's cover photo to S3."""
    url = _cover_image_url(item)
    if not url:
        return
    try:
        import io as _io
        import requests as _requests

        resp = _requests.get(url, timeout=25)
        if resp.status_code != 200:
            return
        if len(resp.content) > MAX_IMAGE_BYTES:
            logger.warning("Cover image too large (%s bytes), skipping upload", len(resp.content))
            return
        bucket = getattr(Config, "S3_BUCKET", "mielenosoitukset.fi")
        from mielenosoitukset_fi.utils.s3 import upload_image_fileobj

        s3_url = upload_image_fileobj(
            bucket, _io.BytesIO(resp.content), f"{item.get('id') or 'event'}.jpg", "demo_pics"
        )
        if s3_url:
            event.image_url = s3_url
    except Exception as exc:
        logger.warning("Failed to download/upload cover image: %s", exc)