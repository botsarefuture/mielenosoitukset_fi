"""Migration: add storage/indexes for distinct visitor counting.

The ``site_analytics_visitors`` collection holds one small document per
(Helsinki-local date, anonymous weekly-salted visitor hash). The hash cannot be
reversed without the application secret, and a TTL index removes documents that
are older than the longest reporting range the dashboards support.
"""

from mielenosoitukset_fi.utils.site_analytics import (
    SITE_ANALYTICS_VISITORS_COLLECTION,
    VISITOR_RETENTION_DAYS,
)


def migrate_visitor_analytics(db):
    """Ensure the visitor collection exists with its query/TTL indexes."""
    collection = db[SITE_ANALYTICS_VISITORS_COLLECTION]
    collection.create_index(
        [("date", 1), ("visitor_hash", 1)],
        unique=True,
        name="site_analytics_visitors_day_hash",
    )
    collection.create_index(
        "date",
        name="site_analytics_visitors_date",
    )
    collection.create_index(
        "expires_at",
        expireAfterSeconds=0,
        name="site_analytics_visitors_expiry",
    )
    return {
        "site_analytics_visitors_indexes": sorted(collection.index_information()),
        "site_analytics_visitors_retention_days": VISITOR_RETENTION_DAYS,
    }
