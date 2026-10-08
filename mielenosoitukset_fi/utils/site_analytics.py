"""Built-in first-party, server-side analytics.

Design goals
------------
* Pageviews are recorded from the Flask request/response lifecycle itself, so
  basic analytics work without cookies, JavaScript, localStorage, or any
  third-party service.
* Only cheap atomic ``$inc`` upserts happen on the request path. All reporting
  reads pre-aggregated counters, so dashboards never scan raw events.
* Pageview counters stay purely aggregate. A second, separate collection keeps
  one small document per (day, anonymous visitor) so a distinct-visitor count is
  possible without ever storing an IP address, a cookie or a user profile.

Data model
----------
One document per (Helsinki-local date, hour, page type, resource, language,
device, referrer) combination in the ``site_analytics`` collection::

    {
        "_id": ObjectId(...),
        "date": "2026-09-22",          # Europe/Helsinki local date
        "hour": 14,                     # Helsinki-local hour (int)
        "page_type": "demonstration",   # what kind of page was viewed
        "resource_id": "abc123",        # path identifier, if any
        "language": "fi",               # UI language served
        "device": "mobile",             # desktop|mobile|tablet|other
        "referrer": "google",           # coarse referrer category
        "count": 12,                    # atomic counter
    }

Events use the same collection with ``event`` instead of ``page_type`` so new
event kinds can be added later without a new schema.

Distinct visitors
-----------------
A "visitor" is a *distinct anonymous visitor inside a reporting period*, not a
person. The identifier is a keyed hash (HMAC-SHA256) of the trusted client IP
and the already-computed coarse device bucket, salted per rotating week so the
same person is never linkable across weeks and no permanent identifier is ever
created. Raw IPs, user-agent strings and cookies are never stored.

One document per (Helsinki-local date, visitor hash) in the
``site_analytics_visitors`` collection::

    {
        "_id": ObjectId(...),
        "date": "2026-09-22",
        "visitor_hash": "9f2c…",        # weekly-salted HMAC, truncated
        "bucket": 3287,                 # which weekly salt produced the hash
        "pageviews": 4,                 # atomic counter
        "expires_at": ISODate(...),     # retention, enforced by a TTL index
    }

Because the salt rotates weekly, a visitor is deduplicated *within* a week. A
period longer than one week can therefore count the same person more than once.
That is a deliberate, bounded trade-off, documented on the dashboard itself.

Filtering (what is NOT counted) lives in :func:`classify_request` and
:func:`should_count_response` and is deliberately simple to read and modify.
Visitors are recorded through the exact same filter, so excluded traffic can
never create a visitor.
"""

import hashlib
import hmac
import math
import re
from bisect import bisect_left
from datetime import date, datetime, time, timedelta, timezone
from ipaddress import ip_address
from urllib.parse import urlsplit

import pytz

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.request_ip import get_client_ip
from mielenosoitukset_fi.utils.time_utils import utcnow

HELSINKI_TZ = pytz.timezone("Europe/Helsinki")

# MongoDB collection used for all aggregate counters.
SITE_ANALYTICS_COLLECTION = "site_analytics"

# MongoDB collection used for distinct-visitor counting. Kept separate from the
# pageview counters so existing pageview queries and numbers cannot change.
SITE_ANALYTICS_VISITORS_COLLECTION = "site_analytics_visitors"

# Daily, anonymous Web Vitals histograms. Documents contain aggregate bucket
# counts only; no visitor, session, URL, metric-instance, or element identifier
# is stored.
WEB_VITALS_COLLECTION = "web_vitals_daily"
WEB_VITALS_RETENTION_DAYS = 400
WEB_VITAL_NAMES = {"CLS", "INP", "LCP", "TTFB"}

# Fixed buckets keep storage cardinality bounded even when the public endpoint
# receives hostile or unusual values. Millisecond metrics retain 50 ms
# resolution through 5 seconds and 250 ms through 10 seconds. CLS retains 0.01
# resolution through 1.0 and 0.1 through the hard 5.0 validation ceiling.
_WEB_VITAL_MS_BUCKETS = tuple(
    list(range(50, 5001, 50))
    + list(range(5250, 10001, 250))
    + [15000, 30000, 60000]
)
_WEB_VITAL_CLS_BUCKETS = tuple(
    [round(value / 100, 2) for value in range(1, 101)]
    + [round(value / 10, 1) for value in range(11, 51)]
)

# Maximum stored length for resource identifiers (demo ids, search terms,
# external hostnames). Anything longer is truncated — analytics counters do
# not need (and should not keep) long free-form values.
MAX_RESOURCE_LENGTH = 200

# --- Distinct visitors -----------------------------------------------------
# How long one visitor identifier stays stable. The salt is derived from the
# application secret plus the week number, so identifiers cannot be correlated
# across weeks and rotating the application secret invalidates them all.
VISITOR_SALT_PERIOD_DAYS = 7

# Length of the stored hash prefix. 16 hex characters is 64 bits: enough that
# colliding two real visitors in one week is negligible, short enough that the
# stored value carries no usable information on its own.
VISITOR_HASH_LENGTH = 16

# Raw visitor documents are only useful for the longest supported range plus a
# comparison period. A TTL index drops them afterwards.
VISITOR_RETENTION_DAYS = 400

# Unspecified / unroutable addresses must never be treated as a shared visitor,
# or every such request would collapse into one "visitor".
_UNKNOWN_CLIENT_ADDRESSES = {"0.0.0.0", "::", ""}

# Events accepted from the browser beacon. Deliberately tiny: these are the
# only browser-side signals with a real dashboard use case. Everything else
# is recorded server-side from actual application actions.
BEACON_EVENT_ALLOWLIST = {"map_interaction", "external_link"}

# Friendly labels for the dashboard events table. Unknown events are shown
# as their raw names.
EVENT_LABELS = {
    "language_change": "Kielenvaihdot",
    "demo_submitted": "Ilmoitetut mielenosoitukset",
    "reminder_subscribe": "Muistutusilmoitukset",
    "follow_organization": "Organisaation seurannat",
    "unfollow_organization": "Seurannan lopetukset (organisaatio)",
    "follow_recurring": "Toistuvien seurannat",
    "unfollow_recurring": "Seurannan lopetukset (toistuva)",
    "contact_message": "Yhteydenotot",
    "volunteer_signup": "Vapaaehtoisilmoitukset",
    "demo_search": "Mielenosoitushaut",
    "map_interaction": "Kartan käytöt",
    "external_link": "Ulkolinkkien klikkaukset",
}

# Coarse device buckets.
DESKTOP = "desktop"
MOBILE = "mobile"
TABLET = "tablet"
BOT = "bot"
OTHER = "other"

# Coarse referrer categories (never store raw referrer URLs).
REFERRER_DIRECT = "direct"
REFERRER_INTERNAL = "internal"
REFERRER_OTHER = "other"

# Friendly labels for the dashboard dropdowns/tables. Values not present
# here are shown as-is (e.g. a brand-new referrer category).
LANGUAGE_LABELS = {"fi": "Suomi", "en": "English", "sv": "Svenska"}
DEVICE_LABELS = {
    DESKTOP: "Työpöytä",
    MOBILE: "Mobiili",
    TABLET: "Tabletti",
    BOT: "Botti",
    OTHER: "Muu",
}
REFERRER_LABELS = {
    REFERRER_DIRECT: "Suoraan",
    REFERRER_INTERNAL: "Sivuston sisältä",
    "google": "Google",
    "facebook": "Facebook",
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "x-twitter": "X (Twitter)",
    "linkedin": "LinkedIn",
    "bing": "Bing",
    "duckduckgo": "DuckDuckGo",
    "youtube": "YouTube",
    "reddit": "Reddit",
    "bluesky": "Bluesky",
    REFERRER_OTHER: "Muu",
}

# Well-known referrer hosts mapped to friendly categories.
_REFERRER_RULES = (
    ("google", "google"),
    ("facebook", "facebook"),
    ("instagram", "instagram"),
    ("tiktok", "tiktok"),
    ("x.com", "x-twitter"),
    ("twitter.com", "x-twitter"),
    ("t.co", "x-twitter"),
    ("linkedin", "linkedin"),
    ("bing", "bing"),
    ("duckduckgo", "duckduckgo"),
    ("youtube", "youtube"),
    ("reddit", "reddit"),
    ("bluesky", "bluesky"),
)

# User-agent fragments used to bucket devices. Deliberately small and
# understandable; this is traffic classification, not fingerprinting.
_BOT_PATTERN = re.compile(
    r"bot|crawl|spider|slurp|facebookexternalhit|embedly|preview|"
    r"python-requests|python-urllib|curl|wget|httpclient|okhttp|go-http|"
    r"headless|lighthouse|pingdom|uptimerobot|monitor",
    re.IGNORECASE,
)
_MOBILE_PATTERN = re.compile(
    r"iphone|ipod|android.*mobile|mobile.*android|windows phone|"
    r"blackberry|bb10|opera mini|opera mobi|iemobile|webos|palm",
    re.IGNORECASE,
)
_TABLET_PATTERN = re.compile(
    r"ipad|kindle|silk|playbook|tablet|nexus (?:7|9|10)|sm-x",
    re.IGNORECASE,
)
_DESKTOP_PATTERN = re.compile(
    r"windows nt|macintosh|mac os x|cros|x11|linux",
    re.IGNORECASE,
)

# Page type for generic public HTML pages (info pages, guides, forms...).
PAGE_TYPE_GENERIC = "page"

# Finnish display labels for page types shown in the admin dashboards.
PAGE_TYPE_LABELS = {
    "index": "Etusivu",
    "demonstration": "Mielenosoitus",
    "demonstrations": "Mielenosoituslista",
    "organization": "Järjestö",
    "city": "Kaupunkisivu",
    "cities": "Kaupunkilista",
    "tag": "Tunniste",
    "calendar": "Kalenteri",
    "today": "Mielenosoitukset tänään",
    "submit": "Ilmoita mielenosoitus",
    "search": "Haku",
    "campaign": "Kampanja",
    PAGE_TYPE_GENERIC: "Muu sivu",
}


def _mongo():
    """Database handle resolved lazily so tests can rebind modules cleanly."""
    return DatabaseManager().get_instance().get_db()


def _collection():
    return _mongo()[SITE_ANALYTICS_COLLECTION]


def _visitor_collection():
    return _mongo()[SITE_ANALYTICS_VISITORS_COLLECTION]


def _web_vitals_collection():
    """Return the daily histogram collection, propagating database setup errors."""
    return _mongo()[WEB_VITALS_COLLECTION]


# ---------------------------------------------------------------------------
# Request classification
# ---------------------------------------------------------------------------


def classify_request(request):
    """Classify a Flask request for analytics purposes.

    Returns ``None`` when the request must not be counted (static assets,
    admin surfaces, health checks, analytics endpoints, obvious bots, ...).
    Otherwise returns a dict with ``page_type``/``event`` plus ``resource_id``,
    ``language``, ``device`` and ``referrer`` fields.

    Everything is derived from the request itself; nothing user-identifying
    is read or stored.
    """
    method = (request.method or "GET").upper()
    if method not in {"GET", "HEAD"}:
        return None

    user_agent = request.headers.get("User-Agent") or ""
    device = classify_device(user_agent)
    if device == BOT:
        return None

    path = request.path or "/"
    classified = classify_path(path)
    if classified is None:
        return None

    classified["language"] = _current_language()
    classified["device"] = device
    classified["referrer"] = classify_referrer(
        request.headers.get("Referer") or "", request.host or ""
    )
    return classified


def classify_path(path):
    """Map a URL path to ``(page_type, resource_id)`` or ``None``.

    ``None`` means "do not track". This function is the single place that
    decides which routes count as analytics traffic; adjust it here.
    """
    if not path:
        return None
    # Normalize: strip trailing slash (except root), ignore query strings.
    path = path.split("?", 1)[0].split("#", 1)[0]
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    segments = [seg for seg in path.split("/") if seg]

    if not segments:
        return {"page_type": "index", "resource_id": None}

    head = segments[0].lower()

    # --- Never count -----------------------------------------------------
    # Static assets, admin area, user accounts, APIs, developer/MCP/board
    # surfaces, health checks and the analytics endpoints themselves.
    if head in {
        "static",
        "admin",
        "users",
        "api",
        "developer",
        "board",
        "mcp",
        "cdn",
        "favicon.ico",
        "health",
        "status",
        "robots.txt",
        "sitemap.xml",
        "manifest.json",
        "demonstrations.rss",
        "screenshot",
    }:
        return None
    if path in {"/favicon.ico"}:
        return None

    # --- Structured public pages -----------------------------------------
    if head == "demonstration" and len(segments) >= 2:
        if len(segments) > 2:
            # Sub-resources (calendar .ics downloads, share pages, ...) are
            # utilities, not demonstration pageviews.
            return None
        return {"page_type": "demonstration", "resource_id": segments[1]}
    if head == "organization" and len(segments) >= 2:
        return {"page_type": "organization", "resource_id": segments[1]}
    if head == "city" and len(segments) >= 2:
        return {"page_type": "city", "resource_id": segments[1]}
    if head == "tag" and len(segments) >= 2:
        return {"page_type": "tag", "resource_id": segments[1]}
    if head == "calendar":
        return {"page_type": "calendar", "resource_id": None}
    if head in {"mielenosoitukset-tanaan"}:
        return {"page_type": "today", "resource_id": None}
    if head == "kampanja":
        return {"page_type": "campaign", "resource_id": "/".join(segments[1:]) or None}
    if head == "pride-nakyvaksi":
        return {"page_type": "campaign", "resource_id": "pride-nakyvaksi"}
    if head == "search_organizations":
        return {"page_type": "search", "resource_id": None}
    if head == "demonstrations":
        return {"page_type": "demonstrations", "resource_id": None}
    if head == "cities":
        return {"page_type": "cities", "resource_id": None}
    if head == "submit":
        return {"page_type": "submit", "resource_id": None}

    # --- Remaining public HTML pages (info, guides, terms, contact...) ----
    return {"page_type": PAGE_TYPE_GENERIC, "resource_id": None}


def should_count_response(response):
    """Whether an *already classified* response should bump the counters."""
    if response is None:
        return False
    status = response.status_code or 0
    if status < 200 or status >= 400:
        return False
    content_type = (response.headers.get("Content-Type") or "").lower()
    if "text/html" not in content_type:
        return False
    return True


def classify_device(user_agent):
    """Bucket a user agent into desktop/mobile/tablet/other (or bot)."""
    ua = (user_agent or "").strip()
    if not ua:
        return OTHER
    if _BOT_PATTERN.search(ua):
        return BOT
    if _MOBILE_PATTERN.search(ua):
        return MOBILE
    if _TABLET_PATTERN.search(ua):
        return TABLET
    if _DESKTOP_PATTERN.search(ua):
        return DESKTOP
    return OTHER


def classify_referrer(referrer, current_host=""):
    """Reduce a Referer header to a coarse category.

    Returns ``direct`` (no referrer), ``internal`` (navigation inside the
    site), a known service name (google, facebook, ...), or ``other``.
    Raw referrer URLs are never persisted.
    """
    referrer = (referrer or "").strip()
    if not referrer:
        return REFERRER_DIRECT

    try:
        ref_host = (urlsplit(referrer).hostname or "").lower()
    except ValueError:
        return REFERRER_OTHER
    if not ref_host:
        return REFERRER_DIRECT

    current = (current_host or "").split(":")[0].split("@")[-1].lower()
    if ref_host == current:
        return REFERRER_INTERNAL
    if ref_host.startswith("www."):
        ref_host = ref_host[4:]

    for needle, category in _REFERRER_RULES:
        if needle in ref_host:
            return category
    return REFERRER_OTHER


def _current_language():
    """Best-effort UI language for this request (no session writes)."""
    try:
        from flask_babel import get_locale

        locale = str(get_locale() or "").strip().lower()
        if locale:
            return locale
    except Exception:
        pass
    try:
        from flask import current_app

        return str(
            current_app.config.get("BABEL_DEFAULT_LOCALE") or "fi"
        ).strip().lower()
    except Exception:
        return "fi"


# ---------------------------------------------------------------------------
# Write path (request-time; must stay cheap and must never break pages)
# ---------------------------------------------------------------------------


def record_pageview_from_request(request, response):
    """Record one pageview for a completed request, if it qualifies.

    Safe to call for every response: non-trackable requests are skipped and
    any storage failure is swallowed (analytics must never break a page).

    Visitor counting reuses this same eligibility decision, so a visitor is
    only ever counted for traffic that also produced a pageview.
    """
    try:
        if not should_count_response(response):
            return False
        classified = classify_request(request)
        if not classified:
            return False
        increment_counter(
            page_type=classified.get("page_type"),
            resource_id=classified.get("resource_id"),
            language=classified.get("language"),
            device=classified.get("device"),
            referrer=classified.get("referrer"),
        )
    except Exception:
        return False

    # Counted separately so a visitor-storage failure can never roll back or
    # delay the pageview counter above.
    try:
        record_visitor_for_request(request, device=classified.get("device"))
    except Exception:
        return False
    return True


# ---------------------------------------------------------------------------
# Visitor identification
# ---------------------------------------------------------------------------


def _visitor_secret():
    """Application secret used to key the visitor hash.

    Uses the same secret that already signs sessions and tokens, through the
    app config when available. It is never stored in the database, so the
    stored hashes cannot be reproduced or reversed from the data alone.
    """
    try:
        from flask import current_app

        secret = current_app.config.get("SECRET_KEY")
        if secret:
            return str(secret).encode("utf-8")
    except Exception:
        pass
    try:
        from config import Config

        if Config.SECRET_KEY:
            return str(Config.SECRET_KEY).encode("utf-8")
    except Exception:
        pass
    return None


def _normalize_client_ip(value):
    """Canonical textual form of a client address, or ``None``.

    IPv4 and IPv6 are normalized to one canonical string so that the many
    spellings of the same address (``::ffff:203.0.113.5``, expanded IPv6, ...)
    collapse into a single visitor instead of several.
    """
    candidate = (value or "").strip()
    if candidate.lower() in _UNKNOWN_CLIENT_ADDRESSES:
        return None
    try:
        parsed = ip_address(candidate)
    except ValueError:
        return None
    # An IPv4-mapped IPv6 address is the same host as the plain IPv4 address.
    mapped = getattr(parsed, "ipv4_mapped", None)
    if mapped is not None:
        parsed = mapped
    if str(parsed) in _UNKNOWN_CLIENT_ADDRESSES:
        return None
    return str(parsed)


def _visitor_salt_bucket(when):
    """Index of the rotating salt period containing ``when``."""
    moment = when or utcnow()
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    local_day = moment.astimezone(HELSINKI_TZ).date()
    epoch = date(2020, 1, 1)
    return (local_day - epoch).days // VISITOR_SALT_PERIOD_DAYS


def visitor_hash(client_ip, device=None, when=None, secret=None):
    """Anonymous, weekly-rotating hash for one client, or ``None``.

    The input is the trusted client IP plus the coarse device bucket that
    :func:`classify_device` already produced. Two different people behind one
    address are therefore two visitors when they use different device types,
    and one visitor when they do not. Browser versions, screen sizes, fonts and
    other fingerprinting signals are deliberately not used.
    """
    normalized = _normalize_client_ip(client_ip)
    if normalized is None:
        return None
    key = secret if secret is not None else _visitor_secret()
    if not key:
        return None

    bucket = _visitor_salt_bucket(when)
    message = f"{bucket}|{normalized}|{(device or '').strip().lower()}".encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()[:VISITOR_HASH_LENGTH]


def record_visitor_for_request(request, device=None, when=None):
    """Count one distinct visitor for an already-counted pageview.

    Returns ``True`` when a visitor was recorded. Any failure is swallowed:
    analytics must never break a page.
    """
    if not visitors_enabled():
        return False
    try:
        client_ip = get_client_ip(default="", request=request)
        identifier = visitor_hash(client_ip, device=device, when=when)
        if not identifier:
            return False

        moment = when or utcnow()
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        local = moment.astimezone(HELSINKI_TZ)

        _visitor_collection().update_one(
            {"date": local.strftime("%Y-%m-%d"), "visitor_hash": identifier},
            {
                "$inc": {"pageviews": 1},
                "$setOnInsert": {
                    "bucket": _visitor_salt_bucket(moment),
                    "expires_at": local.replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                    + timedelta(days=VISITOR_RETENTION_DAYS),
                },
            },
            upsert=True,
        )
        return True
    except Exception:
        return False


def visitors_enabled():
    """Whether distinct-visitor counting is switched on for this app."""
    try:
        from flask import current_app

        return bool(current_app.config.get("SITE_ANALYTICS_VISITORS_ENABLED", True))
    except Exception:
        return True


def increment_counter(page_type=None, event=None, resource_id=None, language=None,
                      device=None, referrer=None, when=None):
    """Atomically bump one aggregate counter document.

    ``when`` defaults to now and is bucketed to Helsinki-local date+hour.
    """
    moment = when or utcnow()
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    local = moment.astimezone(HELSINKI_TZ)

    doc_key = {
        "date": local.strftime("%Y-%m-%d"),
        "hour": int(local.hour),
    }
    if page_type:
        doc_key["page_type"] = page_type
    elif event:
        doc_key["event"] = event
    else:
        return False

    if resource_id:
        doc_key["resource_id"] = str(resource_id)[:MAX_RESOURCE_LENGTH]
    if language:
        doc_key["language"] = str(language)
    if device:
        doc_key["device"] = str(device)
    if referrer:
        doc_key["referrer"] = str(referrer)

    _collection().update_one(doc_key, {"$inc": {"count": 1}}, upsert=True)
    return True


def record_event(event, resource_id=None, language=None, device=None, referrer=None):
    """Record a named analytics event (search, CTA click, ...).

    Kept deliberately thin: events share the aggregate counter collection so
    future event kinds need no new schema or infrastructure.
    """
    try:
        return increment_counter(
            event=event,
            resource_id=resource_id,
            language=language,
            device=device,
            referrer=referrer,
        )
    except Exception:
        return False


def record_event_for_request(event, resource_id=None, request=None):
    """Record an application action as an event, using the current request
    for its language/device/referrer dimensions.

    Only meaningful, deliberate actions should be recorded through this
    helper (submissions, follows, searches...). Bots are skipped and any
    failure is swallowed — analytics must never break an application flow.
    """
    try:
        if request is None:
            from flask import request as _request

            request = _request
        device = classify_device(request.headers.get("User-Agent") or "")
        if device == BOT:
            return False
        return record_event(
            event=event,
            resource_id=resource_id,
            language=_current_language(),
            device=device,
            referrer=classify_referrer(
                request.headers.get("Referer") or "", request.host or ""
            ),
        )
    except Exception:
        return False


def record_beacon_event(payload, request=None):
    """Record an event submitted by the tiny in-page beacon script.

    Guards against junk data:
    * only allowlisted event names are accepted,
    * resource identifiers are trimmed and length-capped,
    * requests with a *cross-origin* referrer are dropped (an in-page beacon
      always shares the site origin, so this removes drive-by spam).
    """
    try:
        if not isinstance(payload, dict):
            return False
        event = str(payload.get("event") or "").strip()
        if event not in BEACON_EVENT_ALLOWLIST:
            return False

        if request is None:
            from flask import request as _request

            request = _request
        referrer_host = ""
        try:
            referrer_host = (urlsplit(request.headers.get("Referer") or "").hostname or "").lower()
        except ValueError:
            return False
        current_host = (request.host or "").split(":")[0].lower()
        if referrer_host and referrer_host != current_host:
            return False

        resource_id = str(payload.get("resource_id") or "").strip()[:MAX_RESOURCE_LENGTH]
        return record_event_for_request(event, resource_id or None, request=request)
    except Exception:
        return False


def _web_vital_buckets(metric):
    """Return unitless upper bounds for CLS, or millisecond bounds otherwise."""
    return _WEB_VITAL_CLS_BUCKETS if metric == "CLS" else _WEB_VITAL_MS_BUCKETS


def record_web_vital(payload, request=None, when=None):
    """Add one anonymous browser metric to a bounded daily histogram.

    ``payload`` must be a dict with ``metric`` and ``value``. Metric names are
    stripped and uppercased; values are converted to floats and must be finite,
    from 0 through 5 for unitless CLS or 0 through 60000 milliseconds for INP,
    LCP, and TTFB. Other payload fields are ignored.

    The route family comes from a public ``Referer`` path whose hostname
    matches the request host, ignoring case, scheme, and port. The device is
    the coarse user-agent bucket; bots are rejected. No raw path, visitor,
    session, metric id, or DOM target is retained.

    ``request`` defaults to the active Flask request. ``when`` defaults to now;
    naive datetimes are treated as UTC. Aggregates use the Helsinki-local date,
    with expiry set to 400 days after that date's local midnight.

    Return ``True`` after the aggregate update succeeds, or ``False`` for
    rejected input or caught request, conversion, and storage errors.
    """
    try:
        if not isinstance(payload, dict):
            return False
        metric = str(payload.get("metric") or "").strip().upper()
        if metric not in WEB_VITAL_NAMES:
            return False
        value = float(payload.get("value"))
        maximum = 5.0 if metric == "CLS" else 60000.0
        if not math.isfinite(value) or value < 0 or value > maximum:
            return False

        if request is None:
            from flask import request as _request

            request = _request
        try:
            referrer = urlsplit(request.headers.get("Referer") or "")
        except ValueError:
            return False
        current_host = (request.host or "").split(":")[0].lower()
        if not referrer.hostname or referrer.hostname.lower() != current_host:
            return False
        classified = classify_path(referrer.path or "/")
        if not classified:
            return False
        device = classify_device(request.headers.get("User-Agent") or "")
        if device == BOT:
            return False

        moment = when or utcnow()
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        local = moment.astimezone(HELSINKI_TZ)
        expires_at = local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
            days=WEB_VITALS_RETENTION_DAYS
        )
        boundaries = _web_vital_buckets(metric)
        bucket_index = bisect_left(boundaries, value)
        bucket_key = f"b{bucket_index:03d}"
        dimensions = {
            "date": local.strftime("%Y-%m-%d"),
            "page_type": classified["page_type"],
            "device": device,
            "metric": metric,
        }
        _web_vitals_collection().update_one(
            dimensions,
            {
                "$inc": {
                    "count": 1,
                    "sum": value,
                    f"histogram.{bucket_key}": 1,
                },
                "$min": {"min": value},
                "$max": {"max": value},
                "$set": {"last_seen_at": moment.astimezone(timezone.utc)},
                "$setOnInsert": {
                    **dimensions,
                    "expires_at": expires_at.astimezone(timezone.utc),
                },
            },
            upsert=True,
        )
        return True
    except (TypeError, ValueError):
        return False
    except Exception:
        return False


def _histogram_percentile(histogram, count, boundaries, percentile):
    """Return the fixed-bucket upper bound for a nearest-rank percentile.

    ``percentile`` is a fraction such as 0.75. ``boundaries`` supplies ascending
    upper bounds for histogram keys ``b000``, ``b001``, and so on. Return
    ``None`` for nonpositive counts, or the last boundary if the bucket counts
    never reach the target rank. Invalid bucket counts propagate conversion
    errors; positive counts require nonempty boundaries.
    """
    if count <= 0:
        return None
    target = math.ceil(count * percentile)
    seen = 0
    for index, boundary in enumerate(boundaries):
        seen += int(histogram.get(f"b{index:03d}", 0) or 0)
        if seen >= target:
            return boundary
    return boundaries[-1]


def get_web_vitals_summary(days=30, minimum_samples=10):
    """Return site-wide approximate Web Vitals percentiles from histograms.

    Combine all routes and devices over ``days`` Helsinki-local dates ending
    today, inclusive; a falsey ``days`` selects 30 days. Return one dict each
    for LCP, INP, CLS, and TTFB, in that order, including empty metrics.

    Each row contains ``metric``, ``count``, ``sufficient``, ``average``, and
    ``p50``/``p75``/``p95``/``p99``. Percentiles are nearest-rank bucket upper
    bounds, or ``None`` below ``minimum_samples`` or with no samples. The
    average is available whenever the count is nonzero. CLS is unitless;
    other values are in milliseconds.

    Database errors and errors converting stored counts or sums propagate.
    """
    match, _start, _end = _match_window(days=days)
    documents = _web_vitals_collection().find(match)
    combined = {
        metric: {"count": 0, "sum": 0.0, "histogram": {}}
        for metric in sorted(WEB_VITAL_NAMES)
    }
    for document in documents:
        metric = document.get("metric")
        if metric not in combined:
            continue
        target = combined[metric]
        target["count"] += int(document.get("count", 0) or 0)
        target["sum"] += float(document.get("sum", 0) or 0)
        for bucket, bucket_count in (document.get("histogram") or {}).items():
            target["histogram"][bucket] = (
                target["histogram"].get(bucket, 0) + int(bucket_count or 0)
            )

    result = []
    for metric in ("LCP", "INP", "CLS", "TTFB"):
        values = combined[metric]
        count = values["count"]
        boundaries = _web_vital_buckets(metric)
        sufficient = count >= minimum_samples
        row = {
            "metric": metric,
            "count": count,
            "sufficient": sufficient,
            "average": (values["sum"] / count) if count else None,
        }
        for label, percentile in (("p50", 0.50), ("p75", 0.75), ("p95", 0.95), ("p99", 0.99)):
            row[label] = (
                _histogram_percentile(
                    values["histogram"], count, boundaries, percentile
                )
                if sufficient
                else None
            )
        result.append(row)
    return result


# ---------------------------------------------------------------------------
# Read path (admin dashboards only)
# ---------------------------------------------------------------------------

_DATE_FMT = "%Y-%m-%d"


def _helsinki_today():
    return utcnow().replace(tzinfo=timezone.utc).astimezone(HELSINKI_TZ)


def _match_window(days=None, start=None, end=None):
    """Build a MongoDB match on the Helsinki-local ``date`` strings."""
    today = _helsinki_today()
    if end is None:
        end = today
    if start is None:
        start = end - timedelta(days=(days - 1) if days else 29)
    return {
        "date": {
            "$gte": start.strftime(_DATE_FMT),
            "$lte": end.strftime(_DATE_FMT),
        }
    }, start, end


def get_overview(days=30, start=None, end=None):
    """Overview counters for the dashboard hero cards.

    Returns totals for today, yesterday, this week, this month and the
    selected window, each paired with the equivalent previous period.
    """
    today = _helsinki_today()
    match, start, end = _match_window(days=days, start=start, end=end)
    del match

    def _range_total(a, b):
        pipeline = [
            {"$match": {"date": {"$gte": a.strftime(_DATE_FMT), "$lte": b.strftime(_DATE_FMT)}}},
            {"$group": {"_id": None, "count": {"$sum": "$count"}}},
        ]
        rows = list(_collection().aggregate(pipeline))
        return rows[0]["count"] if rows else 0

    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    def _pair(current_start, current_end):
        length = (current_end - current_start).days + 1
        previous_end = current_start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=length - 1)
        return {
            "current": _range_total(current_start, current_end),
            "previous": _range_total(previous_start, previous_end),
        }

    return {
        "today": _pair(today, today),
        "yesterday": _range_total(today - timedelta(days=1), today - timedelta(days=1)),
        "week": _pair(week_start, today),
        "month": _pair(month_start, today),
        "window": _pair(start, end),
        "window_days": (end - start).days + 1,
    }


# ---------------------------------------------------------------------------
# Distinct visitors (read path)
# ---------------------------------------------------------------------------


def visitor_data_start():
    """First Helsinki-local date for which visitor data exists, or ``None``.

    Used by the dashboard to tell "no visitors" apart from "visitor tracking
    did not exist yet", so history is never invented.
    """
    try:
        row = _visitor_collection().find_one(
            {}, {"date": 1}, sort=[("date", 1)]
        )
    except Exception:
        return None
    if not row:
        return None
    return row.get("date")


def _visitor_total(start, end):
    """Distinct visitors between two Helsinki-local dates (inclusive)."""
    pipeline = [
        {
            "$match": {
                "date": {
                    "$gte": start.strftime(_DATE_FMT),
                    "$lte": end.strftime(_DATE_FMT),
                }
            }
        },
        {"$group": {"_id": "$visitor_hash"}},
        {"$count": "visitors"},
    ]
    rows = list(_visitor_collection().aggregate(pipeline))
    return rows[0]["visitors"] if rows else 0


def _period(start, end, tracked_from):
    """Visitor pair for one period, or ``None`` values when not yet tracked."""
    if tracked_from is None or tracked_from > end.strftime(_DATE_FMT):
        return {"current": None, "previous": None, "available": False}
    length = (end - start).days + 1
    previous_end = start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=length - 1)
    return {
        "current": _visitor_total(start, end),
        "previous": _visitor_total(previous_start, previous_end),
        "available": True,
    }


def get_visitor_overview(days=30, start=None, end=None):
    """Distinct-visitor counts mirroring :func:`get_overview`.

    Counts are ``None`` for any period that predates visitor tracking, so the
    dashboard can show that the figure is unavailable instead of inventing a
    number from pageviews.
    """
    today = _helsinki_today()
    _, start, end = _match_window(days=days, start=start, end=end)
    tracked_from = visitor_data_start()

    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    return {
        "today": _period(today, today, tracked_from),
        "week": _period(week_start, today, tracked_from),
        "month": _period(month_start, today, tracked_from),
        "window": _period(start, end, tracked_from),
        "window_days": (end - start).days + 1,
        "tracked_from": tracked_from,
        "available": tracked_from is not None,
    }


def get_visitor_series(days=30, start=None, end=None):
    """Distinct visitors per day between two Helsinki-local dates.

    Days before visitor tracking started are reported as ``None`` so a chart
    can leave them visibly empty instead of plotting a false zero.
    """
    match, start, end = _match_window(days=days, start=start, end=end)
    pipeline = [
        {"$match": match},
        {"$group": {"_id": "$date", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    by_date = {
        row["_id"]: row["count"]
        for row in _visitor_collection().aggregate(pipeline)
    }
    tracked_from = visitor_data_start()

    labels, values = [], []
    cursor = start
    while cursor <= end:
        key = cursor.strftime(_DATE_FMT)
        labels.append(cursor.strftime("%d.%m"))
        if tracked_from is None or tracked_from > key:
            values.append(None)
        else:
            values.append(by_date.get(key, 0))
        cursor += timedelta(days=1)
    return {"labels": labels, "values": values, "tracked_from": tracked_from}


def get_traffic_series(days=30, start=None, end=None):
    """Pageviews per day between two Helsinki-local dates (oldest first)."""
    match, start, end = _match_window(days=days, start=start, end=end)
    pipeline = [
        {"$match": match},
        {"$group": {"_id": "$date", "count": {"$sum": "$count"}}},
        {"$sort": {"_id": 1}},
    ]
    by_date = {row["_id"]: row["count"] for row in _collection().aggregate(pipeline)}

    labels, values, previous_total = [], [], 0
    cursor = start
    while cursor <= end:
        key = cursor.strftime(_DATE_FMT)
        labels.append(cursor.strftime("%d.%m"))
        values.append(by_date.get(key, 0))
        cursor += timedelta(days=1)
    return {"labels": labels, "values": values}


def get_top_pages(page_type=None, days=30, start=None, end=None, limit=10,
                  title_resolver=None):
    """Most viewed pages overall or for one ``page_type``.

    ``title_resolver`` maps ``resource_id`` to a display title (used for
    demonstrations and organizations); unresolved ids stay as-is.
    """
    match, start, end = _match_window(days=days, start=start, end=end)
    query = dict(match)
    if page_type:
        query["page_type"] = page_type
        query["resource_id"] = {"$ne": None}
    else:
        query["page_type"] = {"$exists": True}

    pipeline = [
        {"$match": query},
        {"$group": {"_id": {"page_type": "$page_type", "resource_id": "$resource_id"},
                    "count": {"$sum": "$count"}}},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]
    rows = [
        {
            "page_type": row["_id"].get("page_type"),
            "resource_id": row["_id"].get("resource_id"),
            "count": row["count"],
        }
        for row in _collection().aggregate(pipeline)
    ]
    if title_resolver:
        for row in rows:
            row["title"] = title_resolver(row.get("page_type"), row.get("resource_id"))
    else:
        for row in rows:
            row["title"] = row.get("resource_id") or row.get("page_type")
    return rows


def get_breakdown(field, days=30, start=None, end=None, limit=12):
    """Aggregate pageviews grouped by ``language``/``device``/``referrer``."""
    match, _, _ = _match_window(days=days, start=start, end=end)
    pipeline = [
        {"$match": match},
        {"$group": {"_id": f"${field}", "count": {"$sum": "$count"}}},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]
    return [
        {"value": row["_id"] or "other", "count": row["count"]}
        for row in _collection().aggregate(pipeline)
    ]


def get_event_totals(days=30, start=None, end=None, limit=12):
    """Totals per recorded event name in the window, largest first."""
    match, _, _ = _match_window(days=days, start=start, end=end)
    query = dict(match)
    query["event"] = {"$exists": True, "$ne": None}
    pipeline = [
        {"$match": query},
        {"$group": {"_id": "$event", "count": {"$sum": "$count"}}},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]
    return [
        {"event": row["_id"], "count": row["count"]}
        for row in _collection().aggregate(pipeline)
    ]


def get_top_event_resources(event, days=30, start=None, end=None, limit=8):
    """Top resource identifiers for one event (e.g. top search terms)."""
    match, _, _ = _match_window(days=days, start=start, end=end)
    query = dict(match)
    query["event"] = event
    query["resource_id"] = {"$exists": True, "$nin": [None, ""]}
    pipeline = [
        {"$match": query},
        {"$group": {"_id": "$resource_id", "count": {"$sum": "$count"}}},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]
    return [
        {"resource_id": row["_id"], "count": row["count"]}
        for row in _collection().aggregate(pipeline)
    ]


def get_demonstration_identifiers(demo_id):
    """All URL identifiers that can point at a demonstration.

    The public route accepts ObjectId strings, slugs and running numbers, so
    analytics may have counted the same demonstration under different ids.
    """
    from bson import ObjectId

    identifiers = {str(demo_id)}
    try:
        oid = ObjectId(str(demo_id))
    except Exception:
        oid = None
    query = {"$or": [{"_id": oid}] if oid else []}
    if not query["$or"]:
        return identifiers
    query["$or"].append({"slug": str(demo_id)})
    doc = _mongo().demonstrations.find_one(query, {"slug": 1, "running_number": 1})
    if doc:
        identifiers.add(str(doc.get("_id")))
        if doc.get("slug"):
            identifiers.add(str(doc["slug"]))
        if doc.get("running_number") is not None:
            identifiers.add(str(doc["running_number"]))
    return identifiers


def get_demonstration_analytics(demo_id, days=30, start=None, end=None):
    """Analytics for one demonstration: totals, daily series and breakdowns."""
    identifiers = sorted(get_demonstration_identifiers(demo_id))
    match, start, end = _match_window(days=days, start=start, end=end)
    base = dict(match)
    base["page_type"] = "demonstration"
    base["resource_id"] = {"$in": identifiers}

    def _total(date_range):
        query = dict(base)
        query["date"] = date_range
        rows = list(
            _collection().aggregate(
                [{"$match": query}, {"$group": {"_id": None, "count": {"$sum": "$count"}}}]
            )
        )
        return rows[0]["count"] if rows else 0

    total = _total({"$exists": True})

    pipeline = [
        {"$match": base},
        {"$group": {"_id": "$date", "count": {"$sum": "$count"}}},
        {"$sort": {"_id": 1}},
    ]
    by_date = {row["_id"]: row["count"] for row in _collection().aggregate(pipeline)}
    labels, values = [], []
    cursor = start
    while cursor <= end:
        key = cursor.strftime(_DATE_FMT)
        labels.append(cursor.strftime("%d.%m"))
        values.append(by_date.get(key, 0))
        cursor += timedelta(days=1)

    languages = []
    devices = []
    referrers = []
    for field, target in (("language", languages), ("device", devices), ("referrer", referrers)):
        stage = [
            {"$match": base},
            {"$group": {"_id": f"${field}", "count": {"$sum": "$count"}}},
            {"$sort": {"count": -1}},
        ]
        target.extend(
            {"value": row["_id"] or "other", "count": row["count"]}
            for row in _collection().aggregate(stage)
        )

    today = _helsinki_today()
    last_7d = sum(values[-7:])
    return {
        "total": total,
        "last_7d": last_7d,
        "last_28d": sum(values),
        "window_days": (end - start).days + 1,
        "daily_labels": labels,
        "daily_values": values,
        "languages": languages,
        "devices": devices,
        "referrers": referrers,
        "today": _total({"$eq": today.strftime(_DATE_FMT)}),
    }


def summarize_for_demo(demo_id):
    """Small summary for the admin command center analytics card.

    Mirrors the legacy ``_summarize_analytics_doc`` keys (total/last_24h/
    last_7d) using the built-in server-side counters.
    """
    try:
        end = _helsinki_today()
        start = end - timedelta(days=13)
        data = get_demonstration_analytics(demo_id, start=start, end=end)
    except Exception:
        return {"total": 0, "last_24h": 0, "last_7d": 0}
    return {
        "total": data["total"],
        "last_24h": data.get("today", 0) or 0,
        "last_7d": data.get("last_7d", 0),
    }
