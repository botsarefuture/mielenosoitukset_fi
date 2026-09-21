"""Tests for the Facebook event import (Apify-backed form prefill)."""

import sys

import pytest
import requests

from config import Config
from mielenosoitukset_fi.utils.facebook_event_importer import (
    MAX_ADDRESS_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    MAX_ORGANIZER_LENGTH,
    MAX_TITLE_LENGTH,
    FacebookEventImporter,
    FacebookImportError,
    ImportedFacebookEvent,
    parse_event_url,
)

VALID = "https://www.facebook.com/events/123456789"
CANONICAL = "https://www.facebook.com/events/123456789/"


class _FakeApifyResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        if isinstance(self._payload, (dict, list)) or self._payload is None:
            return self._payload
        raise ValueError("Expecting value: line 1 column 1")


class TestParseEventUrl:
    def test_accepts_full_www_url(self):
        assert parse_event_url(VALID) == "https://www.facebook.com/events/123456789/"

    def test_accepts_schemaless_and_mobile_subdomain(self):
        assert (
            parse_event_url("m.facebook.com/events/42")
            == "https://www.facebook.com/events/42/"
        )

    def test_accepts_query_strings_and_trailing_parts(self):
        assert (
            parse_event_url("https://www.facebook.com/events/7?ref=activity_log")
            == "https://www.facebook.com/events/7/"
        )
        assert (
            parse_event_url("https://www.facebook.com/events/7/foo/")
            == "https://www.facebook.com/events/7/"
        )

    def test_rejects_empty_input(self):
        with pytest.raises(FacebookImportError) as exc:
            parse_event_url("   ")
        assert exc.value.code == "missing_url"
        assert exc.value.status_code == 400

    def test_rejects_non_event_facebook_url(self):
        for bad in ("https://www.facebook.com/groups/123", "https://example.com/events/1"):
            with pytest.raises(FacebookImportError) as exc:
                parse_event_url(bad)
            assert exc.value.code == "invalid_url"
            assert exc.value.status_code == 400


class TestFetchEvent:
    def test_not_configured_without_token(self, monkeypatch):
        monkeypatch.delattr(Config, "APIFY_API_TOKEN", raising=False)
        with pytest.raises(FacebookImportError) as exc:
            FacebookEventImporter()._fetch_event(VALID)
        assert exc.value.code == "not_configured"
        assert exc.value.status_code == 503

    @pytest.mark.parametrize(
        "status,code",
        [
            (401, "apify_auth"),
            (403, "apify_auth"),
            (402, "apify_payment"),
            (429, "apify_rate_limit"),
            (404, "apify_unavailable"),
            (408, "apify_timeout"),
            (500, "apify_failed"),
        ],
    )
    def test_http_error_mapping(self, monkeypatch, status, code):
        monkeypatch.setattr(Config, "APIFY_API_TOKEN", "test-token", raising=False)
        monkeypatch.setattr(Config, "APIFY_FACEBOOK_ACTOR_ID", "apify/test", raising=False)

        captured = {}

        def fake_post(url, **kwargs):
            captured["url"] = url
            captured["payload"] = kwargs.get("json")
            captured["headers"] = kwargs.get("headers")
            return _FakeApifyResponse(status_code=status, payload=[])

        monkeypatch.setattr(requests, "post", fake_post)
        with pytest.raises(FacebookImportError) as exc:
            FacebookEventImporter()._fetch_event(VALID)
        assert exc.value.code == code

    def test_builds_endpoint_and_payload(self, monkeypatch):
        monkeypatch.setattr(Config, "APIFY_API_TOKEN", "test-token", raising=False)
        captured = {}

        def fake_post(url, **kwargs):
            captured.update(url=url, payload=kwargs.get("json"), headers=kwargs.get("headers"))
            return _FakeApifyResponse(payload=[{"name": "Mars"}])

        monkeypatch.setattr(requests, "post", fake_post)
        result = FacebookEventImporter()._fetch_event(VALID)

        assert result == {"name": "Mars"}
        assert "run-sync-get-dataset-items" in captured["url"]
        assert captured["payload"]["startUrls"] == [VALID]
        assert captured["headers"]["Authorization"] == "Bearer test-token"

    def test_actor_id_slash_normalized_to_tilde(self, monkeypatch):
        monkeypatch.setattr(Config, "APIFY_API_TOKEN", "test-token", raising=False)
        monkeypatch.setattr(Config, "APIFY_FACEBOOK_ACTOR_ID", "apify/facebook-events-scraper", raising=False)
        captured = {}

        def fake_post(url, **kwargs):
            captured["url"] = url
            return _FakeApifyResponse(payload=[{"name": "Mars"}])

        monkeypatch.setattr(requests, "post", fake_post)
        FacebookEventImporter()._fetch_event(VALID)
        assert "/acts/apify~facebook-events-scraper/run-sync-get-dataset-items" in captured["url"]

    def test_default_actor_id_uses_tilde(self, monkeypatch):
        monkeypatch.setattr(Config, "APIFY_API_TOKEN", "test-token", raising=False)
        monkeypatch.delattr(Config, "APIFY_FACEBOOK_ACTOR_ID", raising=False)
        captured = {}

        def fake_post(url, **kwargs):
            captured["url"] = url
            return _FakeApifyResponse(payload=[{"name": "Mars"}])

        monkeypatch.setattr(requests, "post", fake_post)
        FacebookEventImporter()._fetch_event(VALID)
        assert "/acts/apify~facebook-events-scraper/run-sync-get-dataset-items" in captured["url"]

    def test_network_error_maps_to_apify_network(self, monkeypatch):
        monkeypatch.setattr(Config, "APIFY_API_TOKEN", "test-token", raising=False)

        def fake_post(url, **kwargs):
            raise requests.RequestException("boom")

        monkeypatch.setattr(requests, "post", fake_post)
        with pytest.raises(FacebookImportError) as exc:
            FacebookEventImporter()._fetch_event(VALID)
        assert exc.value.code == "apify_network"
        assert exc.value.status_code == 502

    def test_non_json_response_maps_to_unexpected_response(self, monkeypatch):
        monkeypatch.setattr(Config, "APIFY_API_TOKEN", "test-token", raising=False)

        def fake_post(url, **kwargs):
            return _FakeApifyResponse(payload=ValueError("not json"))

        monkeypatch.setattr(requests, "post", fake_post)
        with pytest.raises(FacebookImportError) as exc:
            FacebookEventImporter()._fetch_event(VALID)
        assert exc.value.code == "unexpected_response"

    def test_empty_or_malformed_results(self, monkeypatch):
        monkeypatch.setattr(Config, "APIFY_API_TOKEN", "test-token", raising=False)
        monkeypatch.setattr(
            requests, "post", lambda url, **kw: _FakeApifyResponse(payload=[])
        )
        with pytest.raises(FacebookImportError) as exc:
            FacebookEventImporter()._fetch_event(VALID)
        assert exc.value.code == "empty_result"
        assert exc.value.status_code == 404

        monkeypatch.setattr(
            requests, "post", lambda url, **kw: _FakeApifyResponse(payload={"name": "x"})
        )
        with pytest.raises(FacebookImportError) as exc:
            FacebookEventImporter()._fetch_event(VALID)
        assert exc.value.code == "unexpected_response"


def _public_item(**overrides):
    item = {
        "name": "Climate March Helsinki",
        "description": "Join us <script>alert(1)</script> and <b>be loud</b>.",
        "utcStartDate": "2026-10-01T12:00:00Z",
        "utcEndDate": "2026-10-01T15:00:00Z",
        "startTime": "3:00 PM",
        "location": {
            "city": "Helsinki, Finland",
            "streetAddress": "Mannerheimintie 5, Helsinki",
            "name": "Senaatintori",
        },
        "organizators": [{"name": "Climate Org"}],
        "organizerCompany": "Other Org",
        "isCanceled": False,
        "isPast": False,
        "eventType": "PUBLIC",
        "isOnline": False,
    }
    item.update(overrides)
    return item


@pytest.fixture
def importer():
    return FacebookEventImporter()


class TestNormalizeEvent:
    def test_full_public_event_normalization(self, importer):
        event = importer._normalize_event(_public_item(), CANONICAL)

        assert event.title == "Climate March Helsinki"
        assert event.start_date == "2026-10-01"
        assert event.start_time == "15:00"
        assert event.end_date == "2026-10-01"
        assert event.end_time == "18:00"
        assert event.city == "Helsinki"
        assert event.address == "Mannerheimintie 5"
        assert event.organizer == "Climate Org"
        assert event.facebook_url == CANONICAL
        assert event.warnings == []
        assert event.missing == []
        assert event.imported == [
            "title",
            "description_html",
            "start_date",
            "start_time",
            "end_date",
            "end_time",
            "city",
            "address",
            "organizer",
            "facebook_url",
        ]

    def test_description_is_sanitized(self, importer):
        event = importer._normalize_event(_public_item(), VALID)
        assert "alert(1)" not in event.description_html
        assert "<strong>be loud</strong>" in event.description_html

    def test_unknown_city_is_not_guessed(self, importer):
        item = _public_item(location={"city": "Atlantis, Finland", "streetAddress": "Example Road 1"})
        event = importer._normalize_event(item, VALID)

        assert event.city == ""
        assert event.address == "Example Road 1"
        assert "city" not in event.imported
        assert "city" in event.missing

    def test_missing_start_stamp_falls_back_to_start_time(self, importer):
        item = _public_item(utcStartDate=None, startTime="5:30 PM")
        event = importer._normalize_event(item, VALID)

        assert event.start_time == "17:30"
        assert event.start_date == ""
        assert "approximate_time" in event.warnings
        assert "start_date" in event.missing
        assert "start_time" in event.imported

    def test_warnings_for_problematic_events(self, importer):
        item = _public_item(
            utcStartDate=None,
            startTime=None,
            isCanceled=True,
            isPast=True,
            isOnline=True,
            eventType="PRIVATE",
        )
        event = importer._normalize_event(item, VALID)
        assert set(event.warnings) == {"canceled", "past", "online", "not_public"}

    def test_length_caps_apply(self, importer):
        item = _public_item(
            name="T" * 500,
            description="d" * 60_000,
            location={
                "city": "Helsinki, Finland",
                "streetAddress": "A" * 500,
                "name": "Senaatintori",
            },
            organizators=[{"name": "O" * 500}],
        )
        event = importer._normalize_event(item, VALID)
        assert len(event.title) == MAX_TITLE_LENGTH
        # Description is no longer truncated; it should preserve the full content
        assert len(event.description_html) >= 60_000
        assert len(event.address) <= MAX_ADDRESS_LENGTH
        assert len(event.organizer) == MAX_ORGANIZER_LENGTH

    def test_organizer_falls_back_to_company(self, importer):
        item = _public_item(organizators=[])
        event = importer._normalize_event(item, VALID)
        assert event.organizer == "Other Org"

    def test_to_dict_contains_expected_keys(self, importer):
        event = importer._normalize_event(_public_item(), VALID)
        data = event.to_dict()
        assert data["title"] == event.title
        assert data["facebook_url"] == event.facebook_url
        assert data["imported"] == event.imported


@pytest.mark.integration
class TestSubmitFacebookImportRoute:
    @pytest.fixture
    def patched_importer(self, monkeypatch):
        def _patch(importer):
            patched = []
            for name in ("basic_routes", "mielenosoitukset_fi.basic_routes"):
                mod = sys.modules.get(name)
                if mod is not None:
                    monkeypatch.setattr(mod, "FacebookEventImporter", lambda: importer)
                    patched.append(mod)
            return patched

        return _patch

    def _post(self, client, **data):
        return client.post("/submit/facebook_import", data=data)

    def test_success_response_shape(self, client, patched_importer):
        event = ImportedFacebookEvent(
            title="Mars",
            description_html="<p>Hi</p>",
            start_date="2026-10-01",
            start_time="15:00",
            city="Helsinki",
            address="Mannerheimintie 5",
            organizer="Climate Org",
            facebook_url=VALID,
            imported=["title", "description_html", "city", "facebook_url", "start_date", "start_time"],
            missing=["end_date", "end_time", "address", "organizer"],
            warnings=["past"],
        )
        patched_importer(type("I", (), {"import_event": lambda self, url: event})())

        resp = self._post(client, url=VALID)
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["success"] is True
        assert payload["event"]["title"] == "Mars"
        assert payload["event"]["facebook_url"] == VALID
        assert payload["message"]
        assert len(payload["fields_summary"]) == 11
        assert payload["fields_summary"][0]["key"] == "title"
        assert payload["warnings"]
        assert payload["warnings"][0]

    def test_known_error_is_mapped(self, client, patched_importer):
        patched_importer(
            type(
                "I",
                (),
                {
                    "import_event": lambda self, url: (_ for _ in ()).throw(
                        FacebookImportError("empty_result", status_code=404)
                    )
                },
            )()
        )
        resp = self._post(client, url=VALID)
        assert resp.status_code == 404
        payload = resp.get_json()
        assert payload["success"] is False
        assert payload["code"] == "empty_result"
        assert payload["error"]

    def test_invalid_url_error(self, client, patched_importer):
        patched_importer(
            type(
                "I",
                (),
                {
                    "import_event": lambda self, url: (_ for _ in ()).throw(
                        FacebookImportError("invalid_url", status_code=400)
                    )
                },
            )()
        )
        resp = self._post(client, url="not-a-link")
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "invalid_url"

    def test_unexpected_exception_returns_internal(self, client, patched_importer):
        def boom(self, url):
            raise RuntimeError("boom")

        patched_importer(type("I", (), {"import_event": boom})())
        resp = self._post(client, url=VALID)
        assert resp.status_code == 500
        payload = resp.get_json()
        assert payload["success"] is False
        assert payload["code"] == "internal"

    def test_missing_url_returns_400(self, client, patched_importer):
        patched_importer(
            type(
                "I",
                (),
                {
                    "import_event": lambda self, url: (_ for _ in ()).throw(
                        FacebookImportError("missing_url", status_code=400)
                    )
                },
            )()
        )
        resp = self._post(client, url="")
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "missing_url"


@pytest.mark.integration
class TestSubmitStampsFacebookProvenance:
    def test_form_submit_stores_facebook_import(self, app, db, seeded_data, external_side_effects, monkeypatch):
        with app.test_client() as c:
            resp = c.post(
                "/submit",
                data={
                    "title": "Facebook Imported Demo",
                    "date": "2026-11-01",
                    "start_time": "12:00",
                    "end_time": "14:00",
                    "city": "Helsinki",
                    "address": "Mannerheimintie 5",
                    "description": "Imported",
                    "submitter_role": "organizer",
                    "submitter_email": "test@example.test",
                    "submitter_name": "Test Henkilö",
                    "accept_terms": "on",
                    "facebook": VALID,
                    "facebook_imported": "1",
                },
            )
            assert resp.status_code in (200, 302)

        demo = db.demonstrations.find_one({"title": "Facebook Imported Demo"})
        assert demo is not None
        assert demo["facebook"] == VALID
        meta = demo["facebook_import"]
        assert meta is not None
        assert meta["url"] == "https://www.facebook.com/events/123456789/"
        assert meta["importer"] == "apify-facebook-events-scraper"
        assert meta["imported_at"]

    def test_form_submit_without_flag_has_no_provenance(self, app, db, seeded_data, external_side_effects):
        with app.test_client() as c:
            resp = c.post(
                "/submit",
                data={
                    "title": "Plain Demo",
                    "date": "2026-11-02",
                    "start_time": "12:00",
                    "end_time": "14:00",
                    "city": "Helsinki",
                    "address": "Mannerheimintie 6",
                    "description": "Plain",
                    "submitter_role": "organizer",
                    "submitter_email": "test@example.test",
                    "submitter_name": "Test Henkilö",
                    "accept_terms": "on",
                    "facebook": VALID,
                },
            )
            assert resp.status_code in (200, 302)

        demo = db.demonstrations.find_one({"title": "Plain Demo"})
        assert demo is not None
        assert "facebook_import" not in demo or demo["facebook_import"] is None


class TestSubmitWizardChooser:
    """The submit wizard starts with an import/manual chooser page and the
    Facebook import section sits at the top of the 'Perustiedot' step."""

    def test_chooser_page_renders_first(self, client):
        resp = client.get("/submit")
        assert resp.status_code == 200
        page = resp.get_data(as_text=True)
        assert 'id="page-1"' in page
        assert 'id="page-2"' in page
        assert 'id="page-6"' in page
        assert "Miten lisäät tapahtuman tiedot?" in page
        assert "Tuo tiedot Facebookista" in page
        assert 'onclick="chooseImport()"' in page
        assert 'onclick="chooseManual()"' in page

    def test_import_section_is_before_title_field(self, client):
        resp = client.get("/submit")
        assert resp.status_code == 200
        page = resp.get_data(as_text=True)
        assert page.index('id="facebook"') < page.index('id="name"')
        assert page.index('id="facebook-import-btn"') < page.index('id="name"')
        assert page.index('id="facebook"') > page.index('id="page-1"')
        assert page.index('id="facebook"') < page.index('id="page-3"')

    def test_progress_steps_count_six(self, client):
        resp = client.get("/submit")
        assert resp.status_code == 200
        page = resp.get_data(as_text=True)
        assert page.count('class="progress-step"') == 6
        assert "Aloitus" in page