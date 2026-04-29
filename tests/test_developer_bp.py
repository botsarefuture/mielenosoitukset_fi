import pytest

from tests.conftest import _client_for_user, _seed_database


@pytest.mark.integration
def test_developer_app_detail_hides_rate_limits_when_enforcement_disabled(seeded_data, developer_client):

    response = developer_client.get(f"/developer/apps/{seeded_data['app_id']}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Rajoitusten valvonta on pois käytöstä tässä ympäristössä." in body
    assert "86400 per day" not in body
    assert "3600 per hour" not in body
    assert "10 per second" not in body
    assert "Sovelluksen oletusrajat" not in body


@pytest.mark.integration
def test_developer_app_detail_shows_actual_rate_limits_when_enforcement_enabled(app_factory, db):
    app = app_factory(ENFORCE_RATELIMIT=True)
    seeded_data = _seed_database(app, db)
    developer_client = _client_for_user(app, seeded_data["developer_id"])

    response = developer_client.get(f"/developer/apps/{seeded_data['app_id']}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "86400 per day" in body
    assert "3600 per hour" in body
    assert "10 per second" in body
    assert "Sovelluksen oletusrajat" in body
