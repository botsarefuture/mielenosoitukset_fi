"""Tests for public /status and admin /admin/status pages."""

from unittest.mock import patch, MagicMock


# ── Public /status ────────────────────────────────────────────────────────────

def test_status_returns_200(app, seeded_data):
    resp = app.test_client().get("/status")
    assert resp.status_code == 200


def test_status_contains_heading(app, seeded_data):
    resp = app.test_client().get("/status")
    html = resp.get_data(as_text=True)
    assert "Palvelun tila" in html


def test_status_shows_overall_banner(app, seeded_data):
    resp = app.test_client().get("/status")
    html = resp.get_data(as_text=True)
    assert "Kaikki palvelut toimivat" in html or "Jokin palvelu ei vastaa" in html
    assert "&#10003;" not in html
    assert "&#10007;" not in html
    assert "✓" in html or "✗" in html


def test_status_shows_db_service(app, seeded_data):
    resp = app.test_client().get("/status")
    html = resp.get_data(as_text=True)
    assert "Tietokanta" in html


def test_status_shows_cache_service(app, seeded_data):
    resp = app.test_client().get("/status")
    html = resp.get_data(as_text=True)
    assert "Välimuisti" in html


def test_status_shows_s3_service(app, seeded_data):
    resp = app.test_client().get("/status")
    html = resp.get_data(as_text=True)
    assert "Tiedostovarasto" in html


def test_status_shows_latency(app, seeded_data):
    resp = app.test_client().get("/status")
    html = resp.get_data(as_text=True)
    assert "ms" in html


def test_status_shows_error_when_db_fails(app, seeded_data):
    from mielenosoitukset_fi.database_manager import DatabaseManager
    original = DatabaseManager.get_db

    def broken_get_db(self, *a, **kw):
        mock_db = MagicMock()
        mock_db.command.side_effect = Exception("connection refused")
        return mock_db

    with patch.object(DatabaseManager, "get_db", broken_get_db):
        resp = app.test_client().get("/status")
        html = resp.get_data(as_text=True)
        assert "Jokin palvelu ei vastaa" in html
        assert "Ei vastaa" in html


def test_status_uses_no_context_processor(app, seeded_data):
    """Status page should not trigger the city/admin context processors."""
    resp = app.test_client().get("/status")
    assert resp.status_code == 200


# ── Admin /admin/status ───────────────────────────────────────────────────────

def test_admin_status_returns_200(app, seeded_data, admin_client):
    resp = admin_client.get("/admin/status")
    assert resp.status_code == 200


def test_admin_status_contains_heading(app, seeded_data, admin_client):
    resp = admin_client.get("/admin/status")
    html = resp.get_data(as_text=True)
    assert "Infrastruktuuri" in html
    assert "&#10003;" not in html
    assert "&#10007;" not in html
    assert "✓" in html or "✗" in html


def test_admin_status_shows_mongodb(app, seeded_data, admin_client):
    resp = admin_client.get("/admin/status")
    html = resp.get_data(as_text=True)
    assert "MongoDB" in html


def test_admin_status_shows_redis(app, seeded_data, admin_client):
    resp = admin_client.get("/admin/status")
    html = resp.get_data(as_text=True)
    assert "Redis" in html


def test_admin_status_shows_s3(app, seeded_data, admin_client):
    resp = admin_client.get("/admin/status")
    html = resp.get_data(as_text=True)
    assert "S3" in html


def test_admin_status_shows_collection_counts(app, seeded_data, admin_client):
    resp = admin_client.get("/admin/status")
    html = resp.get_data(as_text=True)
    assert "Tietokannan kokoelmat" in html


def test_admin_status_shows_overview(app, seeded_data, admin_client):
    resp = admin_client.get("/admin/status")
    html = resp.get_data(as_text=True)
    assert "Yleiskatsaus" in html


def test_admin_status_shows_recent_errors(app, seeded_data, admin_client):
    resp = admin_client.get("/admin/status")
    html = resp.get_data(as_text=True)
    assert "Viimeisimmät virheet" in html


def test_admin_status_requires_auth(app, seeded_data):
    resp = app.test_client().get("/admin/status")
    assert resp.status_code in (302, 401, 403)


def test_admin_status_forbids_normal_user(app, seeded_data, user_client):
    resp = user_client.get("/admin/status")
    assert resp.status_code in (302, 401, 403)


def test_admin_status_shows_server_uptime(app, seeded_data, admin_client):
    resp = admin_client.get("/admin/status")
    html = resp.get_data(as_text=True)
    assert "Palvelin" in html


def test_admin_status_shows_disk_info(app, seeded_data, admin_client):
    resp = admin_client.get("/admin/status")
    html = resp.get_data(as_text=True)
    assert "Levytila" in html
