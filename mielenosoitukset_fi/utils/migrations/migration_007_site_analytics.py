"""Migration: add storage/indexes for built-in first-party site analytics.

The ``site_analytics`` collection stores one aggregate counter document per
(Helsinki-local date, hour, page type/resource, language, device, referrer)
combination. Dashboards aggregate these small documents instead of raw page
view events, so no visitor-level data is ever stored.
"""


def migrate_site_analytics(db):
    """Ensure the site analytics collection exists with its query indexes."""
    db.site_analytics.create_index(
        [("date", 1), ("hour", 1)],
        name="site_analytics_date_hour",
    )
    db.site_analytics.create_index(
        [("page_type", 1), ("resource_id", 1), ("date", 1)],
        name="site_analytics_resource_date",
    )
    db.site_analytics.create_index(
        [("page_type", 1), ("date", 1), ("count", -1)],
        name="site_analytics_top_pages",
    )
    return {
        "site_analytics_indexes": sorted(db.site_analytics.index_information()),
    }
