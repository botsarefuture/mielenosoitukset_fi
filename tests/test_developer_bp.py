import pytest


@pytest.mark.integration
def test_developer_app_detail_shows_actual_rate_limits(seeded_data, developer_client):

    response = developer_client.get(f"/developer/apps/{seeded_data['app_id']}")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "86400 per day" in body
    assert "3600 per hour" in body
    assert "10 per second" in body
    assert "Sovelluksen oletusrajat" in body
