"""Aggregate campaign-tagged public pageviews, without visitor attribution state.

Only named campaign parameters are read. Cookies, profiles, full URLs and
unrelated query strings are not retained. A refresh is another pageview, not
another person, visit, approval or conversion.
"""
import hashlib
import json
import unicodedata
from datetime import timezone

from flask import current_app

from mielenosoitukset_fi.utils import site_analytics as analytics

CAMPAIGN_EVENT = 'campaign_view'
MAX_CAMPAIGN_VALUE_LENGTH = 100
CAMPAIGN_PARAMETERS = {
    'name': ('mtm_campaign', 'matomo_campaign', 'pk_campaign', 'piwik_campaign',
             'utm_campaign', 'utm_source', 'utm_medium'),
    'keyword': ('mtm_kwd', 'mtm_keyword', 'pk_kwd', 'piwik_kwd', 'pk_keyword', 'utm_term'),
    'source': ('mtm_source', 'utm_source'),
    'medium': ('mtm_medium', 'utm_medium'),
    'content': ('mtm_content', 'utm_content'),
    'id': ('mtm_cid', 'utm_id'),
    'group': ('mtm_group',),
    'placement': ('mtm_placement',),
}


def extract_campaign(args):
    """Return validated, case-preserving campaign dimensions or ``None``.

    First nonblank alias wins, with Matomo aliases before legacy/UTM names.
    Conflicting duplicate values and invalid/overlong selected dimensions are
    rejected instead of truncated into another campaign's aggregate.
    """
    campaign = {}
    for dimension, aliases in CAMPAIGN_PARAMETERS.items():
        for alias in aliases:
            values = args.getlist(alias) if hasattr(args, 'getlist') else [args.get(alias)]
            values = [value.strip() for value in values if isinstance(value, str) and value.strip()]
            if not values:
                continue
            if len(set(values)) != 1:
                return None
            value = values[0]
            if (len(value) > MAX_CAMPAIGN_VALUE_LENGTH
                    or any(unicodedata.category(char).startswith('C') for char in value)):
                return None
            campaign[dimension] = value
            break
    return campaign if campaign.get('name') else None


def record_campaign_pageview(request, classified=None, when=None):
    """Record a tagged eligible GET separately from ordinary pageview counts.

    Call only after a successful eligible HTML pageview. Eligibility is checked
    again here so the helper cannot classify API/admin/bot/HEAD traffic as a
    campaign. Storage failure must never fail the page or its pageview count.
    """
    try:
        if (request.method.upper() != 'GET'
                or not current_app.config.get('SITE_ANALYTICS_ENABLED', True)
                or request.headers.get('DNT') == '1'):
            return False
        campaign = extract_campaign(request.args)
        if not campaign:
            return False
        eligible = analytics.classify_request(request)
        if not eligible:
            return False
        encoded = json.dumps(campaign, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        moment = when or analytics.utcnow()
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        local = moment.astimezone(analytics.HELSINKI_TZ)
        key = {
            'date': local.strftime('%Y-%m-%d'), 'hour': int(local.hour),
            'event': CAMPAIGN_EVENT,
            'resource_id': hashlib.sha256(encoded.encode('utf-8')).hexdigest(),
        }
        for dimension in ('language', 'device', 'referrer'):
            if eligible.get(dimension):
                key[dimension] = eligible[dimension]
        analytics._collection().update_one(
            key, {'$inc': {'count': 1}, '$setOnInsert': {'campaign': campaign}}, upsert=True)
        return True
    except Exception:
        return False


def get_campaign_report(days=30, start=None, end=None, limit=20):
    """Return bounded campaign pageview totals in the selected local-day range.

    Counts represent tagged page responses. There is no session-based or
    last-touch attribution, and historical attribution cannot be reconstructed.
    """
    match, _, _ = analytics._match_window(days=days, start=start, end=end)
    match.update(event=CAMPAIGN_EVENT, campaign={'$type': 'object'})
    limit = max(1, min(int(limit), 20))
    pipeline = [
        {'$match': match},
        {'$group': {'_id': '$resource_id', 'count': {'$sum': '$count'},
                    'campaign': {'$first': '$campaign'}}},
        {'$sort': {'count': -1, '_id': 1}},
        {'$limit': limit},
    ]
    rows = []
    for row in analytics._collection().aggregate(pipeline):
        metadata = row.get('campaign') or {}
        # Keep this report a plain-text data contract even for historical rows.
        safe = {name: value for name, value in metadata.items()
                if name in CAMPAIGN_PARAMETERS and isinstance(value, str)
                and len(value) <= MAX_CAMPAIGN_VALUE_LENGTH}
        if safe.get('name'):
            rows.append({'campaign': safe, 'count': row['count']})
    return rows
