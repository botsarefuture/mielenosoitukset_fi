"""Public campaign presentation and confirmation preserve server-side guarantees."""

from datetime import timedelta
import json

import pytest

from mielenosoitukset_fi.utils.time_utils import utcnow


def test_campaign_fallback_is_readable_and_contains_no_public_procurement_detail(admin_client):
    response = admin_client.get('/kampanja/')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'data-react-island="campaign-page"' in body
    for copy in ('Mielenosoitukset.fi näkyviin kymmeniin kaupunkeihin', 'Näin voit auttaa', 'Mistä on kyse', 'Tietoa keräyksestä', 'Aikataulu', 'Usein kysyttyä'):
        assert copy in body
    for detail in ('1 889,94', '775,81', '740,41', '373,72', 'Mahdollisuuksia vaikuttaa'):
        assert detail not in body
    assert 'href="#vapaaehtoiseksi"' in body
    assert 'href="/ker%C3%A4ys"' in body


@pytest.mark.parametrize('status', ['success', 'invalid', 'expired'])
def test_confirmation_keeps_token_validation_and_has_readable_nojs_html(client, db, status):
    token = 'confirmation-example-' + status
    if status != 'invalid':
        db.volunteers.insert_one({
            'name': '<script>Not rendered</script>', 'email': 'confirmation@example.test',
            'confirmed': False, 'confirmation_token': token,
            'confirmation_expires': utcnow() + timedelta(hours=1 if status == 'success' else -1),
        })
    response = client.get('/kampanja/confirm/' + token)
    assert response.status_code == (200 if status == 'success' else 400)
    body = response.get_data(as_text=True)
    assert 'id="confirmation-title"' in body
    assert 'data-react-island="campaign-confirmation"' in body
    assert '🎉' not in body and '💪' not in body and 'virallisesti' not in body
    assert '<script>Not rendered</script>' not in body
    assert response.headers['Cache-Control'] == 'private, no-store'
    assert response.headers['X-Robots-Tag'] == 'noindex, nofollow'
    if status == 'success':
        assert 'Ilmoittautumisesi on vahvistettu' in body
        volunteer = db.volunteers.find_one({'email': 'confirmation@example.test'})
        assert volunteer['confirmed'] is True and 'confirmation_token' not in volunteer
        assert client.get('/kampanja/confirm/' + token).status_code == 400
    elif status == 'expired':
        assert 'Vahvistuslinkki on vanhentunut' in body
        assert db.volunteers.find_one({'email': 'confirmation@example.test'})['confirmed'] is False
    else:
        assert 'Vahvistuslinkki ei ole voimassa' in body

