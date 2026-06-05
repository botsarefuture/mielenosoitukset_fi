import unicodedata

from mielenosoitukset_fi.utils.variables import CITY_LIST


def normalize_city_key(city: str | None) -> str:
    """Return a stable ASCII key for a Finnish municipality name."""
    if not city:
        return ""

    normalized = unicodedata.normalize("NFKD", str(city).strip().casefold())
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return "-".join(part for part in ascii_text.replace("_", "-").split() if part)


CITY_KEY_TO_NAME = {normalize_city_key(city): city for city in CITY_LIST}
CITY_NAME_TO_KEY = {city: normalize_city_key(city) for city in CITY_LIST}


def valid_city_key(city_key: str | None) -> bool:
    return bool(city_key) and city_key in CITY_KEY_TO_NAME
