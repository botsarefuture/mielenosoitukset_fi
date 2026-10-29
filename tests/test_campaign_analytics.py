"""Campaign attribution counts tagged pageviews, never people or conversions."""
from datetime import datetime, timedelta, timezone

import pytest
from werkzeug.datastructures import MultiDict

from mielenosoitukset_fi.utils import campaign_analytics as campaigns
from mielenosoitukset_fi.utils import site_analytics as analytics


def test_campaign_matomo_alias_precedence_and_supported_dimensions():
    params = MultiDict({
        'mtm_campaign': ' Pride 2026 ', 'pk_campaign': 'legacy', 'utm_campaign': 'fallback',
        'mtm_keyword': 'banner', 'utm_term': 'old', 'mtm_source': 'newsletter',
        'mtm_medium': 'email', 'mtm_content': 'top', 'mtm_cid': 'ad42',
        'mtm_group': 'public', 'mtm_placement': 'footer', 'email': 'private@example.test'})
    assert campaigns.extract_campaign(params) == {
        'name': 'Pride 2026', 'keyword': 'banner', 'source': 'newsletter',
        'medium': 'email', 'content': 'top', 'id': 'ad42', 'group': 'public', 'placement': 'footer'}


@pytest.mark.parametrize('alias', ['mtm_campaign', 'matomo_campaign', 'pk_campaign',
    'piwik_campaign', 'utm_campaign', 'utm_source', 'utm_medium'])
def test_campaign_name_aliases(alias):
    assert campaigns.extract_campaign(MultiDict({alias: 'example'}))['name'] == 'example'


@pytest.mark.parametrize('alias', ['mtm_kwd', 'mtm_keyword', 'pk_kwd', 'piwik_kwd', 'pk_keyword', 'utm_term'])
def test_campaign_keyword_aliases(alias):
    assert campaigns.extract_campaign(MultiDict({'mtm_campaign': 'example', alias: 'word'}))['keyword'] == 'word'


@pytest.mark.parametrize('params', [
    {'unknown': 'campaign'}, {'mtm_source': 'source-only'}, {'mtm_campaign': ' '},
    {'mtm_campaign': 'x' * 101}, {'mtm_campaign': 'control\x00name'},
    {'mtm_campaign': 'ok', 'mtm_medium': 'x' * 101},
])
def test_invalid_campaign_values_are_not_silently_merged(params):
    assert campaigns.extract_campaign(MultiDict(params)) is None


def test_conflicting_duplicate_campaign_parameter_is_rejected():
    assert campaigns.extract_campaign(MultiDict([('mtm_campaign', 'one'), ('mtm_campaign', 'two')])) is None
    assert campaigns.extract_campaign(MultiDict([('mtm_campaign', 'one'), ('mtm_campaign', 'one')])) == {'name': 'one'}


def test_campaign_storage_is_aggregate_bounded_and_refreshes_are_pageviews(app, db):
    db.site_analytics.delete_many({})
    moment = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)
    with app.test_request_context('/?mtm_campaign=Pride&mtm_source=mail&password=secret&email=private@example.test',
                                  headers={'User-Agent': 'Mozilla/5.0 (X11; Linux)'}):
        from flask import request
        for _ in range(2):
            assert campaigns.record_campaign_pageview(request, when=moment)
    rows = list(db.site_analytics.find({'event': 'campaign_view'}))
    assert len(rows) == 1 and rows[0]['count'] == 2
    assert rows[0]['campaign'] == {'name': 'Pride', 'source': 'mail'}
    assert len(rows[0]['resource_id']) == 64
    assert 'page_type' not in rows[0]
    assert not any(value in str(rows[0]) for value in ('private@example.test', 'password', 'secret', 'cookie', 'visitor_hash'))
    report = campaigns.get_campaign_report(start=moment.date(), end=moment.date())
    assert report == [{'campaign': {'name': 'Pride', 'source': 'mail'}, 'count': 2}]
    assert campaigns.get_campaign_report(start=moment.date()+timedelta(days=1), end=moment.date()+timedelta(days=1)) == []


@pytest.mark.parametrize('path,method,headers', [
    ('/admin/analytics/?mtm_campaign=test', 'GET', {}),
    ('/api/demonstrations?mtm_campaign=test', 'GET', {}),
    ('/?mtm_campaign=test', 'HEAD', {}), ('/?mtm_campaign=test', 'POST', {}),
    ('/?mtm_campaign=test', 'GET', {'DNT': '1'}),
    ('/?mtm_campaign=test', 'GET', {'User-Agent': 'Googlebot'}),
    ('/?mtm_campaign=test', 'GET', {'Purpose': 'prefetch'}),
])
def test_campaign_tracking_excludes_non_pageviews_and_dnt(app, db, path, method, headers):
    db.site_analytics.delete_many({})
    with app.test_request_context(path, method=method, headers=headers):
        from flask import request
        assert not campaigns.record_campaign_pageview(request)
    assert db.site_analytics.count_documents({'event': 'campaign_view'}) == 0


def test_disabled_campaign_tracking_and_storage_failure_are_safe(app, db, monkeypatch):
    with app.test_request_context('/?mtm_campaign=test'):
        from flask import request
        app.config['SITE_ANALYTICS_ENABLED'] = False
        assert not campaigns.record_campaign_pageview(request)
        app.config['SITE_ANALYTICS_ENABLED'] = True
        def fail():
            raise RuntimeError('storage unavailable')
        monkeypatch.setattr(analytics, '_collection', fail)
        assert not campaigns.record_campaign_pageview(request)


def test_campaign_pageviews_remain_separate_from_overview(app, db):
    db.site_analytics.delete_many({})
    analytics.increment_counter(page_type='index')
    with app.test_request_context('/?mtm_campaign=example'):
        from flask import request
        assert campaigns.record_campaign_pageview(request)
    assert analytics.get_overview(days=1)['today']['current'] == 1
    assert sum(analytics.get_traffic_series(days=1)['values']) == 1
    assert campaigns.get_campaign_report(days=1)[0]['count'] == 1
