"""The allowed WebAuthn origins configured for a deployment must reach the app.

Production serves passkeys from both ``https://mielenosoitukset.fi`` and
``https://www.mielenosoitukset.fi`` and lists both in configuration. App
creation used to replace that list with the single primary origin, so a
registration started on the www host failed origin validation.
"""

from __future__ import annotations

import pytest

APEX = "https://example.fi"
WWW = "https://www.example.fi"


@pytest.fixture
def configured_origins(monkeypatch):
    from config import Config

    monkeypatch.setattr(Config, "WEBAUTHN_ORIGIN", APEX)
    monkeypatch.setattr(Config, "WEBAUTHN_RP_ID", "example.fi")
    monkeypatch.setattr(Config, "WEBAUTHN_ALLOWED_ORIGINS", [WWW, APEX])
    return [WWW, APEX]


def test_configured_origin_list_survives_app_creation(app_factory, configured_origins):
    app = app_factory()

    assert app.config["WEBAUTHN_ALLOWED_ORIGINS"] == configured_origins


def test_overriding_only_the_primary_origin_rederives_the_list(app_factory):
    app = app_factory(WEBAUTHN_ORIGIN="https://test.example.fi")

    assert app.config["WEBAUTHN_ALLOWED_ORIGINS"] == ["https://test.example.fi"]


def test_an_explicit_allowed_origins_override_wins(app_factory, configured_origins):
    explicit = ["https://explicit.example.fi"]

    app = app_factory(WEBAUTHN_ALLOWED_ORIGINS=explicit)

    assert app.config["WEBAUTHN_ALLOWED_ORIGINS"] == explicit
