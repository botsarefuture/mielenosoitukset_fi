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
