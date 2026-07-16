from mielenosoitukset_fi.utils.cities import CITY_KEY_TO_NAME, normalize_city_key
from mielenosoitukset_fi.utils.time_utils import utcnow


DEFAULT_ACTIVE_CITY_NAMES = [
    "Tampere",
    "Kuopio",
    "Turku",
    "Kokkola",
    "Porvoo",
    "Pieksämäki",
    "Jyväskylä",
    "Pietarsaari",
    "Vaasa",
    "Seinäjoki",
    "Lappeenranta",
    "Sastamala",
    "Savonlinna",
    "Oulu",
    "Rovaniemi",
]
DEFAULT_ACTIVE_CITY_KEYS = {
    normalize_city_key(city)
    for city in DEFAULT_ACTIVE_CITY_NAMES
    if normalize_city_key(city) in CITY_KEY_TO_NAME
}


def enabled_city_settings(db):
    return list(
        db.city_settings.find(
            {"enabled": True},
            {"city_key": 1, "name": 1, "summary": 1, "contact_instructions": 1},
        ).sort("name", 1)
    )


def enabled_city_keys(db):
    configured = {
        doc["city_key"]: bool(doc.get("enabled"))
        for doc in db.city_settings.find({}, {"city_key": 1, "enabled": 1})
        if doc.get("city_key")
    }
    configured_enabled = {city_key for city_key, enabled in configured.items() if enabled}
    default_without_override = DEFAULT_ACTIVE_CITY_KEYS - set(configured)
    return configured_enabled | default_without_override


def enabled_city_names(db):
    names = {
        CITY_KEY_TO_NAME[city_key]
        for city_key in enabled_city_keys(db)
        if city_key in CITY_KEY_TO_NAME
    }
    for doc in enabled_city_settings(db):
        city_key = doc.get("city_key")
        if city_key in CITY_KEY_TO_NAME:
            names.add(doc.get("name") or CITY_KEY_TO_NAME[city_key])
    return sorted(names)


def upsert_city_setting(db, city_key, enabled, actor_id=None):
    city_key = normalize_city_key(city_key)
    if city_key not in CITY_KEY_TO_NAME:
        return None

    now = utcnow()
    payload = {
        "city_key": city_key,
        "name": CITY_KEY_TO_NAME[city_key],
        "enabled": bool(enabled),
        "updated_at": now,
    }
    if actor_id:
        payload["updated_by"] = str(actor_id)

    db.city_settings.update_one(
        {"city_key": city_key},
        {
            "$set": payload,
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return payload
