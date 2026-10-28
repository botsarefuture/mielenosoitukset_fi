"""RSS is a public listing consumer, including filtered cache and HTTP contracts."""
from copy import deepcopy
from datetime import date, timedelta
import xml.etree.ElementTree as ET

from bson import ObjectId
import pytest


def seed_feed(db, seeded_data):
    base = db.demonstrations.find_one({'_id': seeded_data['demo_id']})
    db.demonstrations.delete_many({})
    rows = []
    for number, changes in enumerate(({}, {'city': 'Turku'}, {'tags': ['climate']},
                                     {'hide': True}, {'approved': False}, {'rejected': True},
                                     {'cancelled': True}, {'approved': None},
                                     {'date': (date.today() - timedelta(days=1)).isoformat()})):
        row = deepcopy(base)
        row.update(_id=ObjectId(), title=f'Feed event {number}', city='Helsinki',
                   date=(date.today() + timedelta(days=number + 1)).isoformat(),
                   formatted_date='', approved=True, hide=False, rejected=False,
                   cancelled=False, tags=['pride'], parent=None, slug=f'feed-event-{number}')
        row.update(changes)
        rows.append(row)
    db.demonstrations.insert_many(rows)
    return rows


def feed_items(response):
    assert response.status_code == 200
    assert response.mimetype == 'application/rss+xml'
    return ET.fromstring(response.data).findall('channel/item')


@pytest.mark.parametrize('args,expected', [({}, [0, 1, 2]), ({'city': ' helSINKI '}, [0, 2]),
    ({'tag': 'PRIDE'}, [0, 1]), ({'city': 'Helsinki', 'tag': 'pride'}, [0]),
    ({'city': '.*'}, []), ({'tag': 'pri.*'}, []),
    ({'include_cancelled': 'true', 'in_past': 'true', 'approved': 'false'}, [0, 1, 2])])
def test_feed_exposes_only_upcoming_public_events_and_literal_filters(client, db, seeded_data, args, expected):
    seed_feed(db, seeded_data)
    items = feed_items(client.get('/demonstrations.rss', query_string=args))
    assert [item.findtext('title').split(':')[0] for item in items] == [f'Feed event {i}' for i in expected]


def test_feed_caps_soonest_events_and_has_safe_text_canonical_links_and_unique_guids(client, db, seeded_data):
    rows = seed_feed(db, seeded_data)
    base = rows[0]
    db.demonstrations.delete_many({})
    for number in reversed(range(55)):
        row = {**base, '_id': ObjectId(), 'slug': f'feed-{number}',
               'date': (date.today() + timedelta(days=number)).isoformat(),
               'title': f'Name <{number}> & title', 'description': '<img src=x onerror=alert(1)> & text'}
        db.demonstrations.insert_one(row)
    items = feed_items(client.get('/demonstrations.rss'))
    assert len(items) == 50
    assert items[0].findtext('title').startswith('Name <0> & title:')
    assert items[-1].findtext('title').startswith('Name <49> & title:')
    assert len({item.findtext('guid') for item in items}) == 50
    assert all(item.find('guid').get('isPermaLink') == 'false' for item in items)
    assert '/demonstration/feed-0' in items[0].findtext('link')
    assert '&lt;img' in items[0].findtext('description')
    assert '<img' not in items[0].findtext('description')


def test_feed_cache_keeps_scopes_separate_and_evaluates_conditional_requests(client, db, seeded_data):
    seed_feed(db, seeded_data)
    origin = 'https://rss.example.test'
    whole = client.get('/demonstrations.rss', base_url=origin)
    pride = client.get('/demonstrations.rss?tag=pride', base_url=origin)
    turku = client.get('/demonstrations.rss?city=Turku', base_url=origin)
    assert [len(feed_items(r)) for r in (whole, pride, turku)] == [3, 2, 1]
    assert whole.headers['ETag'] != pride.headers['ETag'] != turku.headers['ETag']
    again = client.get('/demonstrations.rss?tag=pride', base_url=origin)
    assert again.data == pride.data and again.headers['ETag'] == pride.headers['ETag']
    for etag in (pride.headers['ETag'], 'W/' + pride.headers['ETag'], '*'):
        response = client.get('/demonstrations.rss?tag=pride', base_url=origin, headers={'If-None-Match': etag})
        assert response.status_code == 304 and not response.data
    assert client.get('/demonstrations.rss?city=Turku', base_url=origin,
                      headers={'If-None-Match': pride.headers['ETag']}).status_code == 200
    assert client.get('/demonstrations.rss?tag=pride', base_url=origin).status_code == 200


@pytest.mark.parametrize('path,feed_query', [('/demonstrations', ''), ('/city/Helsinki', '?city=Helsinki'),
    ('/tag/pride', '?tag=pride')])
def test_public_listing_links_have_their_scope_and_feed_autodiscovery(client, path, feed_query):
    response = client.get(path)
    assert response.status_code == 200
    source = response.get_data(as_text=True)
    assert 'type="application/rss+xml"' in source
    assert 'href="/demonstrations.rss' + feed_query + '"' in source
    assert '"rssUrl": "/demonstrations.rss' + feed_query + '"' in source


def test_feed_matches_translated_tags_without_exposing_private_source_fields(client, db, seeded_data):
    rows = seed_feed(db, seeded_data)
    db.demonstrations.update_one({'_id': rows[2]['_id']}, {'$set': {
        'translations': {'en': {'tags': ['pride']}}, 'private_notes': 'DO NOT PUBLISH'}})
    response = client.get('/demonstrations.rss?tag=pride')
    assert len(feed_items(response)) == 3
    assert b'DO NOT PUBLISH' not in response.data


def test_admin_feed_cannot_bypass_public_visibility(admin_client, db, seeded_data):
    seed_feed(db, seeded_data)
    assert len(feed_items(admin_client.get('/demonstrations.rss?include_cancelled=true'))) == 3
