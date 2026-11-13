"""Public fundraising details; incomplete configuration never opens donations."""

import json
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo


def _https_url(value):
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if any(char.isspace() or ord(char) < 32 for char in value) or "\\" in value:
        return ""
    try:
        parsed = urlsplit(value)
        parsed.port  # Reject malformed port numbers as well as invalid hosts.
        if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password:
            return value
    except ValueError:
        pass
    return ""


def fundraising_details(data=None, *, today=None):
    if data is None:
        try:
            data = json.loads((Path(__file__).parent / "data/fundraising.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
    if not isinstance(data, dict):
        data = {}
    details = {
        key: data.get(key, "").strip() if isinstance(data.get(key), str) else ""
        for key in ("collection_number", "recipient", "iban", "reference", "payment_url")
    }
    # Only deliberately configured HTTPS destinations can become links.
    details["payment_url"] = _https_url(details["payment_url"])
    mobilepay = data.get("mobilepay_links", [])
    details["mobilepay_links"] = [
        {"label": entry.get("label", "").strip() or f"MobilePay {index + 1}", "url": _https_url(entry.get("url"))}
        for index, entry in enumerate(mobilepay if isinstance(mobilepay, list) else [])
        if isinstance(entry, dict) and isinstance(entry.get("label", ""), str)
    ]
    try:
        start = date.fromisoformat(data.get("start_date", ""))
        end = date.fromisoformat(data.get("end_date", ""))
    except (TypeError, ValueError):
        start = end = None
    try:
        planned_start = date.fromisoformat(data.get("planned_start_date", ""))
        planned_end = date.fromisoformat(data.get("planned_end_date", ""))
    except (TypeError, ValueError):
        planned_start = planned_end = None
    complete = bool(
        start and end and start <= end
        and details["collection_number"]
        and (details["payment_url"] or (details["recipient"] and details["iban"]) or any(link["url"] for link in details["mobilepay_links"]))
    )
    confirmed = data.get("details_confirmed") is True and complete
    today = today or datetime.now(ZoneInfo("Europe/Helsinki")).date()
    details.update(
        start_date=start,
        end_date=end,
        confirmed=confirmed,
        display_start_date=start if confirmed else planned_start,
        display_end_date=end if confirmed else planned_end,
        is_preparation=not confirmed or data.get("publication_state") not in {"active", "closed"},
        show_header_link=data.get("show_header_link") is True,
        can_donate=bool(confirmed and data.get("publication_state") == "active" and start <= today <= end),
    )
    return details


def fundraising_bar(data=None, *, today=None):
    """Settings for the front-page bar, from the same fundraising configuration.

    The bar is off unless `show_bar` is true. Dates are the shown dates, so the
    opening can be announced before the details are confirmed. `donations_open`
    is the date-independent part of `can_donate`: the bar may only say the
    collection is running when it is confirmed and active.
    """
    if data is None:
        try:
            data = json.loads((Path(__file__).parent / "data/fundraising.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
    if not isinstance(data, dict):
        data = {}
    details = fundraising_details(data, today=today)
    start, end = details["display_start_date"], details["display_end_date"]
    return {
        "enabled": data.get("show_bar") is True and bool(start and end),
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        "donations_open": bool(details["confirmed"] and data.get("publication_state") == "active"),
    }
