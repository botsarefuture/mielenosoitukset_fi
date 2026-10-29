"""Pageview summaries must not include unrelated event counters."""
from datetime import timedelta

import pytest
from werkzeug.wrappers import Response

from mielenosoitukset_fi.utils import site_analytics as sa


def test_all_pageview_reports_exclude_events(db, app):
    db.site_analytics.delete_many({})
    now = sa.utcnow()
    for offset in (0, 1):
        when = now - timedelta(days=offset)
        for _ in range(3):
            sa.increment_counter(page_type='index', language='fi', device='desktop', referrer='direct', when=when)
        for event in ('rss_fetch', 'rss_not_modified', 'demo_search', 'campaign_view'):
            for _ in range(5):
                sa.increment_counter(event=event, language='fi', device='desktop', referrer='direct', when=when)
    assert sa.get_overview(days=2)['window']['current'] == 6
    assert sum(sa.get_traffic_series(days=2)['values']) == 6
    for field in ('language', 'device', 'referrer'):
        assert sum(row['count'] for row in sa.get_breakdown(field, days=2)) == 6
    assert sum(row['count'] for row in sa.get_event_totals(days=2)) == 40


@pytest.mark.parametrize('status,expected', [(200, True), (201, True), (301, False), (302, False), (304, False), (404, False), (500, False)])
def test_only_successful_html_responses_are_pageviews(status, expected):
    assert sa.should_count_response(Response('body', status=status, content_type='text/html')) is expected


@pytest.mark.parametrize('method,headers', [('HEAD', {}), ('GET', {'Purpose': 'prefetch'}), ('GET', {'Sec-Purpose': 'prefetch;prerender'})])
def test_non_view_requests_do_not_add_pageviews(app, method, headers):
    with app.test_request_context('/info', method=method, headers={'User-Agent': 'Mozilla/5.0 Firefox', **headers}):
        from flask import request
        assert sa.classify_request(request) is None


def test_tagged_page_counts_once_and_survives_visitor_failure(app, client, db, monkeypatch):
    from flask import redirect
    from mielenosoitukset_fi.utils.campaign_analytics import get_campaign_report
    db.site_analytics.delete_many({})
    app.add_url_rule('/analytics-check-redirect', 'analytics_check_redirect', lambda: redirect('/info'))
    def fail_visitor(*args, **kwargs):
        raise RuntimeError('Visitor store unavailable')
    monkeypatch.setattr(sa, 'record_visitor_for_request', fail_visitor)
    headers = {'User-Agent': 'Mozilla/5.0 Firefox'}
    assert client.get('/info?mtm_campaign=test', headers=headers).status_code == 200
    assert client.head('/info?mtm_campaign=test', headers=headers).status_code == 200
    assert client.get('/analytics-check-redirect?mtm_campaign=test', headers=headers).status_code == 302
    assert client.get('/info?mtm_campaign=test', headers={**headers, 'Purpose': 'prefetch'}).status_code == 200
    assert sa.get_overview(days=1)['today']['current'] == 1
    rows = get_campaign_report(days=1)
    assert len(rows) == 1 and rows[0]['count'] == 1
