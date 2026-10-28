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
    scope = {'city': city.casefold(), 'tag': tag.casefold(), 'day': day,
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
    return response.make_conditional(request)
