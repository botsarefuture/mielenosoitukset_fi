"""Pure policy/message snapshots for the urgent admin Telegram outbox.

No database writes, transport, credentials or channel IDs belong in this module.
"""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from html import escape
from zoneinfo import ZoneInfo

from bson import ObjectId

from mielenosoitukset_fi.utils.city_assignment import city_review_deadline
from mielenosoitukset_fi.utils.demo_seo import parse_demo_date

HELSINKI = ZoneInfo("Europe/Helsinki")
DEFAULT_URGENT_HOURS = 48
DEFAULT_CRITICAL_HOURS = 24


def _utc(value):
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def review_event_start(demo):
    """Return an unambiguous Helsinki start as UTC, never a guessed midnight."""
    day = parse_demo_date(demo.get("date"))
    raw_clock = demo.get("start_time")
    if day is None or not isinstance(raw_clock, str):
        return None
    clock = None
    for pattern in ("%H:%M:%S", "%H:%M"):
        try:
            clock = datetime.strptime(raw_clock.strip(), pattern).time()
            break
        except ValueError:
            continue
    if clock is None:
        return None
    local = datetime.combine(day, clock)
    candidates = {
        local.replace(tzinfo=HELSINKI, fold=fold).astimezone(UTC)
        for fold in (0, 1)
    }
    valid = {instant for instant in candidates
             if instant.astimezone(HELSINKI).replace(tzinfo=None) == local}
    # Zero matches means a spring gap; two means an unspecified autumn fold.
    return next(iter(valid)) if len(valid) == 1 else None


def _label(value, limit, fallback):
    text = " ".join(value.split())[:limit] if isinstance(value, str) else ""
    return escape(text or fallback)


def _local_time(value):
    return value.astimezone(HELSINKI).strftime("%d.%m.%Y klo %H.%M %Z")


def build_urgent_review_alert(
    demo, now, *, has_message=False,
    urgent_hours=DEFAULT_URGENT_HOURS, critical_hours=DEFAULT_CRITICAL_HOURS,
):
    """Build the current safe snapshot, or None when no new alert is eligible.

    Existing messages receive explicit non-urgent/terminal snapshots rather than
    being deleted or recreated. A delivery worker must retain the same provider
    message ID and re-read canonical state before sending/editing.
    """
    if any(isinstance(value, bool) or not isinstance(value, int)
           for value in (urgent_hours, critical_hours)) or not 0 < critical_hours < urgent_hours:
        raise ValueError("Urgency thresholds must be positive ordered integer hours")
    now = _utc(now)
    if now is None:
        raise ValueError("An explicit UTC reference time is required")
    demo_id = demo.get("_id")
    if not isinstance(demo_id, (str, ObjectId)) or not ObjectId.is_valid(demo_id):
        return None
    demo_id = str(ObjectId(demo_id))
    start = review_event_start(demo)
    urgency = None
    threshold = None
    handled_at = None
    terminal = next((state for flag, state in (
        ("cancelled", "cancelled"), ("approved", "approved"), ("rejected", "rejected")
    ) if demo.get(flag)), None)
    if terminal:
        if not has_message:
            return None
        state = terminal
        labels = {"cancelled": "Peruttu", "approved": "Hyväksytty", "rejected": "Hylätty"}
        heading = labels[state]
        decision = demo.get("moderation_decision") or {}
        if state == "cancelled":
            handled_at = _utc(demo.get("cancelled_at"))
        elif decision.get("status") == state:
            handled_at = _utc(decision.get("at"))
    elif demo.get("in_past") and (start is None or start <= now):
        state, heading = "archived", "Arkistoitu – tarkista käsittelytilanne"
    elif start is None:
        state, heading = "invalid_time", "Aloitusaika vaatii tarkistuksen"
    elif start <= now:
        state, heading = "started", "Mielenosoitus on alkanut – käsittely kesken"
    elif start - now >= timedelta(hours=urgent_hours):
        state, heading = "rescheduled", "Ei enää kiireellinen – ajankohta myöhemmin"
    else:
        state = "pending"
        urgency = "critical" if start - now < timedelta(hours=critical_hours) else "urgent"
        # Labels follow configured thresholds, not fixed wording for24/48 only.
        threshold = critical_hours if urgency == "critical" else urgent_hours
        heading = f"Kiireellinen moderointi – alle {threshold} h"
    if state != "pending" and not has_message:
        return None

    assignment = demo.get("city_assignment") or {}
    # Decisions clear assignments. Their absence then says nothing about who
    # owned the review; do not relabel a resolved city review as national.
    responsibility = (
        None if terminal and not assignment else
        "city" if assignment and not assignment.get("escalated") else "national"
    )
    deadline = _utc(city_review_deadline(demo))
    lines = [
        f"<b>{heading}</b>",
        _label(demo.get("title"), 200, "Mielenosoitus"),
        f"Kaupunki: {_label(demo.get('city'), 100, 'Ei tiedossa')}",
        f"Alkaa: {_local_time(start)}" if start else "Alkaa: aikaa ei voitu varmistaa",
    ]
    if responsibility:
        lines.append("Vastuu: kaupunkiadminit" if responsibility == "city" else "Vastuu: kansallinen tiimi")
    if deadline:
        lines.append(f"Käsittelyn määräaika: {_local_time(deadline)}")
    if handled_at:
        lines.append(f"Käsitelty: {_local_time(handled_at)}")
    lines.append(f'<a href="https://mielenosoitukset.fi/admin/demo/review/{demo_id}">Avaa adminissa</a>')
    text = "\n".join(lines)
    return {
        "demo_id": demo_id, "state": state, "urgency": urgency, "threshold_hours": threshold,
        "responsibility": responsibility, "starts_at": start,
        "review_deadline_at": deadline, "handled_at": handled_at,
        "text": text, "text_sha256": sha256(text.encode("utf-8")).hexdigest(),
    }
