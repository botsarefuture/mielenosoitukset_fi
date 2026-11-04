from urllib.parse import urlparse

from mielenosoitukset_fi.utils.moderation_mail import personalize_moderation_messages
from tests.test_system_teams import teams


def test_each_recipient_has_distinct_private_registered_links(app, db, seeded_data):
    demo = seeded_data['pending_demo_id']
    with app.test_request_context():
        messages = personalize_moderation_messages(db, demo, [{'template_name': 'admin_demo_approve_notification.html',
            'subject': 'Moderation QA', 'recipients': ['alice@example.test', 'bob@example.test'], 'context': {'title': 'QA'}}])
    assert len(messages) == 2
    assert messages[0]['context']['approve_link'] != messages[1]['context']['approve_link']
    records = list(db.magic_links.find({'intended_recipient': {'$ne': None}, 'demo_id': str(demo)}))
    assert len(records) == 6
    assert {row['intended_recipient']['username'] for row in records} == {'alice', 'bob'}
    for message in messages:
        assert '@' not in message['context']['approve_link']


def test_bearer_decision_records_recipient_without_claiming_verified_identity(app, db, seeded_data):
    demo = seeded_data['pending_demo_id']
    db.cases.update_one({'_id': seeded_data['case_id']}, {'$set': {'demo_id': demo}})
    with app.test_request_context():
        messages = personalize_moderation_messages(db, demo, [{'template_name': 'admin_demo_approve_notification.html',
            'subject': 'Moderation QA', 'recipients': ['bob@example.test'], 'context': {'title': 'QA'}}])
    path = urlparse(messages[0]['context']['approve_link']).path
    client = app.test_client()
    assert client.get(path).status_code == 200
    assert client.post(path).status_code == 302
    actor = db.demonstrations.find_one({'_id': demo})['moderation_decision']['actor']
    assert actor['authentication'] == 'bearer_link'
    assert actor['user_id'] is None
    assert actor['link_recipient']['username'] == 'bob'
    case = db.cases.find_one({'_id': seeded_data['case_id']})
    assert case['case_history'][-1]['metadata']['actor']['link_recipient']['username'] == 'bob'
    assert 'Linkki lähetetty: bob' == case['case_history'][-1]['user']


def test_escalation_retry_keeps_personal_links_and_skips_acknowledged_recipients(app, db, seeded_data, monkeypatch):
    from types import SimpleNamespace
    from mielenosoitukset_fi.scripts.escalate_city_assignments import _queue_escalation_email
    from mielenosoitukset_fi.utils.time_utils import utcnow
    from jinja2 import Environment, FileSystemLoader
    monkeypatch.setattr('mielenosoitukset_fi.utils.moderation_mail.national_recipients', lambda db: [
        {'email': 'alice@example.test'}, {'email': 'bob@example.test'}])
    demo_id = seeded_data['pending_demo_id']
    db.demonstrations.update_one({'_id': demo_id}, {'$set': {'city_assignment': {'assigned_at': utcnow()}}})
    demo = db.demonstrations.find_one({'_id': demo_id})
    attempts = []
    def send(job, **kwargs):
        attempts.append(job.recipients[0])
        if len(attempts) == 2:
            raise RuntimeError('temporary delivery failure')
        return True
    sender = SimpleNamespace(_instance_id='qa', _env=Environment(loader=FileSystemLoader('mielenosoitukset_fi/templates/emails')),
                             send_email=send)
    with app.test_request_context():
        assert not _queue_escalation_email(sender, db, demo, 24)
        saved = db.demonstrations.find_one({'_id': demo_id})['city_assignment']['escalation_delivery']
        assert saved['delivered_indices'] == [0]
        assert _queue_escalation_email(sender, db, demo, 24)
    assert attempts == ['alice@example.test', 'bob@example.test', 'bob@example.test']
    final = db.demonstrations.find_one({'_id': demo_id})['city_assignment']['escalation_delivery']
    assert final['messages'] == saved['messages'] and final['delivered_indices'] == [0, 1]
