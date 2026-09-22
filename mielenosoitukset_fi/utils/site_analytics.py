"""Built-in first-party, server-side analytics.

Design goals
------------
* Pageviews are recorded from the Flask request/response lifecycle itself, so
  basic analytics work without cookies, JavaScript, localStorage, or any
  third-party service.
* Only cheap atomic ``$inc`` upserts happen on the request path. All reporting
  reads pre-aggregated counters, so dashboards never scan raw events.
* Nothing visitor-identifying is stored: no IPs, no user agents, no cookies,
  no per-visitor documents. Every tracked request only bumps a counter.

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

Filtering (what is NOT counted) lives in :func:`classify_request` and
:func:`should_count_response` and is deliberately simple to read and modify.
"""

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import pytz

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.time_utils import utcnow

HELSINKI_TZ = pytz.timezone("Europe/Helsinki")

# MongoDB collection used for all aggregate counters.
SITE_ANALYTICS_COLLECTION = "site_analytics"

# Maximum stored length for resource identifiers (demo ids, search terms,
# external hostnames). Anything longer is truncated — analytics counters do
# not need (and should not keep) long free-form values.
MAX_RESOURCE_LENGTH = 200

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
        return True
    except Exception:
        return False


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
