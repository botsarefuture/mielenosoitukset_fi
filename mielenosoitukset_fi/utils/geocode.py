"""Geocoding helpers for resolving demonstration address coordinates.

The site uses the free ``geocode.maps.co`` API to turn an address + city into
a latitude/longitude pair used by the demonstration map. All geocoding goes
through :func:`geocode_address` so the API key, URL encoding, timeout, and
error handling live in exactly one place.
"""

import logging
from typing import Optional, Tuple

import requests

from config import Config

logger = logging.getLogger(__name__)

GEOCODE_BASE_URL = "https://geocode.maps.co/search"

# Small timeout so a slow/blackholed geocoder never blocks request handling.
GEOCODE_TIMEOUT_SECONDS = 10


def geocode_address(
    address: str,
    city: str,
    country: str = "Finland",
) -> Optional[Tuple[str, str]]:
    """Resolve ``address`` into a ``(latitude, longitude)`` string pair.

    The query is passed to the API through ``requests`` ``params`` so every
    character of the address (umlauts, spaces, commas, ampersands in Finnish
    addresses) is correctly URL-encoded. Returns ``None`` when the input is
    empty, the API errors out (missing/invalid key, rate limit, 4xx/5xx), or
    the response contains no usable coordinates.

    Parameters
    ----------
    address : str
        Street address of the demonstration.
    city : str
        City (municipality) the address belongs to.
    country : str, optional
        Country appended to the query, by default ``"Finland"``.

    Returns
    -------
    tuple of str or None
        ``(latitude, longitude)`` as JSON string values, or ``None`` if the
        lookup failed.
    """
    if not address or not city:
        return None

    query = ", ".join(part for part in (address, city, country) if part)

    params = {"q": query}
    api_key = getattr(Config, "GEOCODE_API_KEY", None)
    if api_key:
        params["api_key"] = api_key

    try:
        response = requests.get(
            GEOCODE_BASE_URL,
            params=params,
            timeout=GEOCODE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        results = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Geocode lookup failed for %r: %s", query, exc)
        return None

    if not results:
        logger.info("Geocode lookup returned no results for %r", query)
        return None

    # geocode.maps.co returns {lat: "60.1", lon: "24.9", ...}. Guard against
    # missing keys: do not fall back to a truthy "None" placeholder string.
    first = results[0] or {}
    latitude = first.get("lat")
    longitude = first.get("lon")
    if not latitude or not longitude:
        logger.info("Geocode lookup returned coordinates without lat/lon for %r", query)
        return None

    return str(latitude), str(longitude)