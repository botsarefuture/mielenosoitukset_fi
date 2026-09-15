import pytest


MANUAL_PAGES = [
    "index",
    "dashboard",
    "demos",
    "recurring",
    "organizations",
    "users",
    "users/add",
    "users/about_roles",
    "stats",
    "security",
    "support",
    "faq",
]


@pytest.mark.parametrize("page", MANUAL_PAGES)
def test_manual_pages_render(app, admin_client, page):
    resp = admin_client.get(f"/admin/manual/{page}")
    assert resp.status_code == 200, f"{page} returned {resp.status_code}"
    body = resp.get_data(as_text=True)
    assert "Käyttöohje" in body or "Ohje" in body or "käyttöohje" in body


def test_manual_index_render(app, admin_client):
    resp = admin_client.get("/admin/manual/")
    assert resp.status_code == 200


def test_manual_requires_login(app, client):
    resp = client.get("/admin/manual/dashboard")
    assert resp.status_code in (302, 401, 403)
