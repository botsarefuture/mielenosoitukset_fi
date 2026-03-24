from urllib.request import urlopen

import pytest

from tests.conftest import _seed_database


@pytest.mark.integration
def test_public_pages_render_over_real_http(app, db, live_server):
    seeded_data = _seed_database(app, db)

    with urlopen(f"{live_server}/", timeout=10) as index_response:
        index_body = index_response.read().decode("utf-8")
        assert index_response.status == 200
    assert "Climate March Helsinki" in index_body

    with urlopen(
        f"{live_server}/demonstration/{seeded_data['demo_id']}",
        timeout=10,
    ) as detail_response:
        detail_body = detail_response.read().decode("utf-8")
        assert detail_response.status == 200
    assert "Climate March Helsinki" in detail_body

    with urlopen(
        f"{live_server}/organization/{seeded_data['org_id']}",
        timeout=10,
    ) as organization_response:
        organization_body = organization_response.read().decode("utf-8")
        assert organization_response.status == 200
    assert "Test Organization" in organization_body
