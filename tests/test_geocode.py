import pytest

from mielenosoitukset_fi.utils.geocode import GEOCODE_BASE_URL, geocode_address


class _FakeResponse:
    def __init__(self, payload=None, error=None):
        self._payload = payload if payload is not None else []
        self._error = error

    def raise_for_status(self):
        if self._error is not None:
            raise self._error

    def json(self):
        return self._payload


@pytest.fixture
def capture_geocode_request(monkeypatch):
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["params"] = kwargs.get("params", {})
        return _FakeResponse()

    monkeypatch.setattr("requests.get", fake_get)
    return captured


class TestGeocodeAddressHelper:
    def test_query_is_sent_through_params_not_raw_url(self, capture_geocode_request):
        result = geocode_address("Mikonkatu & Siltakatu 8", "Oulu")

        assert result is None
        assert capture_geocode_request["url"] == GEOCODE_BASE_URL
        assert "q" not in capture_geocode_request["url"]
        assert (
            capture_geocode_request["params"]["q"]
            == "Mikonkatu & Siltakatu 8, Oulu, Finland"
        )
        assert capture_geocode_request["params"]["api_key"]

    def test_returns_coordinates_from_first_result(self, monkeypatch):
        monkeypatch.setattr(
            "requests.get",
            lambda url, **kwargs: _FakeResponse(
                [{"lat": "60.1699", "lon": "24.9384", "display_name": "Helsinki"}]
            ),
        )

        assert geocode_address("Mannerheimintie 1", "Helsinki") == (
            "60.1699",
            "24.9384",
        )

    def test_returns_none_for_empty_results(self, monkeypatch):
        monkeypatch.setattr("requests.get", lambda url, **kwargs: _FakeResponse([]))

        assert geocode_address("Nowhere 1", "Helsinki") is None

    def test_returns_none_when_lat_or_lon_missing(self, monkeypatch):
        # Regression: older code used .get("lat", "None") which returned the
        # truthy string "None" and then saved bogus coordinates.
        monkeypatch.setattr(
            "requests.get",
            lambda url, **kwargs: _FakeResponse([{"lat": "60.1699"}]),
        )

        assert geocode_address("Mannerheimintie 1", "Helsinki") is None

    def test_returns_none_when_api_errors(self, monkeypatch):
        import requests

        monkeypatch.setattr(
            "requests.get",
            lambda url, **kwargs: _FakeResponse(
                error=requests.exceptions.ConnectionError("boom")
            ),
        )

        assert geocode_address("Mannerheimintie 1", "Helsinki") is None

    def test_returns_none_without_making_request_for_missing_city(
        self, monkeypatch
    ):
        def fail(*args, **kwargs):
            raise AssertionError("requests.get should not be called")

        monkeypatch.setattr("requests.get", fail)

        assert geocode_address("", "") is None


class TestGeocodeAdminEndpoint:
    def test_returns_coordinates_for_logged_in_admin(self, admin_client):
        resp = admin_client.post(
            "/api/admin/demo/geocode",
            json={"address": "Mikonkatu 8", "city": "Helsinki"},
        )

        assert resp.status_code == 200
        assert resp.get_json() == {"latitude": "60.1699", "longitude": "24.9384"}

    def test_requires_login(self, client, seeded_data):
        resp = client.post(
            "/api/admin/demo/geocode",
            json={"address": "Mikonkatu 8", "city": "Helsinki"},
        )

        assert resp.status_code in (401, 403, 302)

    def test_requires_address_and_city(self, admin_client):
        assert (
            admin_client.post("/api/admin/demo/geocode", json={}).status_code == 400
        )
        assert (
            admin_client.post(
                "/api/admin/demo/geocode", json={"address": "Mikonkatu 8"}
            ).status_code
            == 400
        )