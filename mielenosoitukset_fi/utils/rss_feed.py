"""Read-only public RSS consumer; shares listing visibility, never admin scope."""
from copy import deepcopy
from datetime import date
import hashlib
import html
import json
import re
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

from flask import Response, current_app, request, url_for

from mielenosoitukset_fi.utils.cache import cache, skip_cache_public_only
from mielenosoitukset_fi.utils.database import DEMO_FILTER
from mielenosoitukset_fi.utils.public_pagination import PUBLIC_DEMONSTRATION_ORDER


def demonstration_feed(collection, event_path):
    """Return up to 50 upcoming public events, optionally scoped by city/tag."""
    city = request.args.get('city', '').strip()
    tag = request.args.get('tag', '').strip()
    # Version the key to avoid serving historical unfiltered responses. Include
    # the origin because RSS links must be absolute, and the day for future scope.
    day = date.today().isoformat()
    # Unicode casefold is broader than Mongo's case-insensitive literal regex
    # (for example straße/strasse), so cache exact stripped filter values.
    scope = {'city': city, 'tag': tag, 'day': day,
             'origin': request.url_root}
    key = 'rss:public-v2:' + hashlib.sha256(json.dumps(scope, sort_keys=True).encode()).hexdigest()
    use_cache = not skip_cache_public_only()
    body = cache.get(key) if use_cache else None
    if body is None:
        query = deepcopy(DEMO_FILTER)
        query['date'] = {'$gte': day}
        if city:
            query['city'] = {'$regex': '^' + re.escape(city) + '$', '$options': 'i'}
        if tag:
            pattern = {'$regex': '^' + re.escape(tag) + '$', '$options': 'i'}
            query['$and'].append({'$or': [{'tags': pattern}] + [
                {f'translations.{locale}.tags': pattern}
                for locale in current_app.config.get('BABEL_SUPPORTED_LOCALES', ['fi'])]})
        projection = {field: 1 for field in ('_id', 'title', 'date', 'formatted_date',
                      'description', 'city', 'address', 'start_time', 'end_time',
                      'parent', 'slug', 'running_number')}
        events = collection.find(query, projection).sort(PUBLIC_DEMONSTRATION_ORDER).limit(50)
        feed = ET.Element('rss', version='2.0')
        channel = ET.SubElement(feed, 'channel')
        ET.SubElement(channel, 'title').text = 'Mielenosoitukset'
        ET.SubElement(channel, 'link').text = url_for('demonstrations', _external=True, **{
            name: value for name, value in (('city', city), ('tag', tag)) if value})
        ET.SubElement(channel, 'description').text = 'Tulevat julkiset mielenosoitukset.'
        ET.SubElement(channel, 'language').text = 'fi-fi'
        for event in events:
            item = ET.SubElement(channel, 'item')
            event_date = event.get('formatted_date') or event.get('date') or ''
            ET.SubElement(item, 'title').text = f"{event.get('title') or 'Mielenosoitus'}: {event_date}"
            link = urljoin(request.url_root, event_path(event))
            ET.SubElement(item, 'link').text = link
            # Stable occurrence identity even if a canonical slug changes or
            # several recurring occurrences share the same series URL.
            ET.SubElement(item, 'guid', isPermaLink='false').text = 'urn:moso:demonstration:' + str(event['_id'])
            details = [event_date, event.get('start_time'), event.get('end_time'),
                       event.get('city'), event.get('address'), event.get('description')]
            # RSS descriptions are HTML fragments. Escape untrusted data once at
            # that layer; ElementTree then handles the outer XML encoding.
            ET.SubElement(item, 'description').text = '<br>'.join(
                html.escape(str(value)) for value in details if value)
        body = ET.tostring(feed, encoding='utf-8', xml_declaration=True)
        if use_cache:
            cache.set(key, body, timeout=300)
    response = Response(body, content_type='application/rss+xml; charset=utf-8')
    response.set_etag(hashlib.sha256(body).hexdigest())
    response.headers['Cache-Control'] = 'public, max-age=300, must-revalidate'
    # Evaluate conditional headers per request, not inside a cached Response.
    response.make_conditional(request)
    record_feed_request(response.status_code, scope)
    return response


def record_feed_request(status, scope):
    """Count fetches and approximate reader-days without pageviews or cookies.

    A reader is a weekly HMAC of the trusted IP, deduplicated until Helsinki
    midnight in the shared cache. Proxies/NAT/cache eviction make this an
    estimate of fetching clients, never a subscription/person count.
    """
    try:
        if (request.method != 'GET' or status not in (200, 304)
                or not current_app.config.get('SITE_ANALYTICS_ENABLED', True)
                or request.headers.get('DNT') == '1'):
            return
        from datetime import datetime, timedelta, timezone
        from urllib.parse import urlencode
        from mielenosoitukset_fi.utils import site_analytics as analytics

        resource = urlencode({name: scope[name].casefold() for name in ('city', 'tag') if scope[name]}) or 'all'
        analytics.record_event('rss_fetch', resource_id=resource, language='fi')
        if status == 304:
            analytics.record_event('rss_not_modified', resource_id=resource, language='fi')
        if not analytics.visitors_enabled():
            return
        moment = analytics.utcnow()
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        identifier = analytics.visitor_hash(analytics.get_client_ip(default='', request=request),
                                           device='rss', when=moment)
        if not identifier:
            return
        local = moment.astimezone(analytics.HELSINKI_TZ)
        midnight = analytics.HELSINKI_TZ.localize(datetime.combine(
            local.date() + timedelta(days=1), datetime.min.time()))
        key = f'rss-reader-day:v1:{local.date().isoformat()}:{identifier}'
        # Keep this global across scopes: fetching city + tag feeds is still one
        # estimated client-day. No IP/UA/cookie/account data is persisted.
        if cache.add(key, True, timeout=max(1, int((midnight - moment).total_seconds()))):
            if not analytics.record_event('rss_reader_day', language='fi'):
                cache.delete(key)
    except Exception:
        # Analytics and cache failures must never prevent feed delivery.
        pass
