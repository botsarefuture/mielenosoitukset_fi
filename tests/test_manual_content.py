import re

import pytest


@pytest.mark.parametrize(
    "page,expected",
    [
        ("users/add", ["Luo uusi käyttäjä", "Sähköposti", "Kaupunkiadmin"]),
        ("users/about_roles", ["global_admin", "city_admin", "translator", "god", "Kääntäjä"]),
    ],
)
def test_manual_updated_content_present(app, admin_client, page, expected):
    resp = admin_client.get(f"/admin/manual/{page}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    for needle in expected:
        assert needle in body, f"{page} missing {needle!r}"


def test_manual_base_has_no_broken_image_refs(app, admin_client):
    resp = admin_client.get("/admin/manual/users/add")
    body = resp.get_data(as_text=True)
    bad = re.findall(r"<img[^>]*src=\"[^\"]*manual/[^\"]*\"", body)
    assert not bad, f"manual add page still references screenshots: {bad}"


def test_manual_base_renders_mobile_toggle(app, admin_client):
    resp = admin_client.get("/admin/manual/dashboard")
    body = resp.get_data(as_text=True)
    assert "manual-sidebar-toggle" in body
    assert "toggleManualSidebar" in body