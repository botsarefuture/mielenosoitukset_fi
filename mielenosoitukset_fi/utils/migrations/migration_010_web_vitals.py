"""Migration: add bounded aggregate storage for anonymous Web Vitals."""

from mielenosoitukset_fi.utils.site_analytics import WEB_VITALS_COLLECTION


def migrate_web_vitals(db):
    """Create the uniqueness, reporting, and TTL indexes for daily histograms."""
    collection = db[WEB_VITALS_COLLECTION]
    collection.create_index(
        [("date", 1), ("page_type", 1), ("device", 1), ("metric", 1)],
        unique=True,
        name="web_vitals_daily_dimensions",
    )
    collection.create_index(
        [("date", 1), ("metric", 1)],
        name="web_vitals_daily_reporting",
    )
    collection.create_index(
        "expires_at",
        expireAfterSeconds=0,
        name="web_vitals_daily_expiry",
    )
    return {
        "web_vitals_indexes": sorted(collection.index_information()),
    }
