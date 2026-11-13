"""Signing out needs a POST with the form token; a GET must never end a session."""

import re
from pathlib import Path

import pytest

PROFILE = "/users/profile/"


def _signed_in(client):
    return client.get(PROFILE, follow_redirects=False).status_code == 200


def _token(client):
    return client.get("/api/session").get_json()["logout_token"]


def test_get_logout_keeps_the_session_and_shows_a_confirmation(user_client):
    response = user_client.get("/users/auth/logout")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    html = response.get_data(as_text=True)
    assert 'method="post"' in html and 'name="logout_token"' in html
    assert _signed_in(user_client)


@pytest.mark.parametrize("headers", [
    {"Sec-Purpose": "prefetch"},
    {"Sec-Purpose": "prefetch;anonymous-client-ip"},
    {"Sec-Purpose": "prerender"},
    {"Purpose": "prefetch"},
    {"Sec-Fetch-Mode": "cors"},
    {"Sec-Fetch-Mode": "no-cors"},
])
def test_prefetch_gets_an_empty_answer_and_keeps_the_session(user_client, headers):
    response = user_client.get("/users/auth/logout", headers=headers)
    assert response.status_code == 204 and not response.data
    assert _signed_in(user_client)


def test_post_without_or_with_wrong_token_is_refused_and_keeps_the_session(user_client):
    for data in ({}, {"logout_token": "nope"}):
        response = user_client.post("/users/auth/logout", data=data)
        assert response.status_code == 302 and response.headers["Location"].endswith("/users/auth/logout")
    assert _signed_in(user_client)


def test_token_from_another_account_or_secret_is_refused(app, user_client, admin_client):
    other = _token(admin_client)
    assert user_client.post("/users/auth/logout", data={"logout_token": other}).status_code == 302
    assert _signed_in(user_client)


def test_post_with_token_signs_out(user_client):
    token = _token(user_client)
    response = user_client.post("/users/auth/logout", data={"logout_token": token})
    assert response.status_code == 302 and "/users/auth/login" in response.headers["Location"]
    assert not _signed_in(user_client)


def test_anonymous_never_gets_a_token_and_get_redirects(client):
    assert "logout_token" not in client.get("/api/session").get_json()
    assert client.get("/users/auth/logout").status_code == 302
    assert client.post("/users/auth/logout", data={"logout_token": "x"}).status_code == 302


def test_server_rendered_pages_use_a_post_form_not_a_link(user_client):
    html = user_client.get("/").get_data(as_text=True)
    assert 'href="/users/auth/logout"' not in html
    assert re.search(r'<form method="post" action="/users/auth/logout"', html)


def test_react_menu_and_footer_source_use_post_and_no_hover_open():
    root = Path(__file__).resolve().parent.parent / "frontend" / "src"
    menu = (root / "components" / "header" / "UserMenu.tsx").read_text()
    assert "onPointerEnter" not in menu and "onPointerLeave" not in menu
    assert '<form method="post"' in menu and "logout_token" in menu
    footer = (root / "app" / "Footer.tsx").read_text()
    assert '<form method="post"' in footer and "logoutToken" in footer
    css = (root.parent.parent / "mielenosoitukset_fi" / "static" / "css" / "public-header.css").read_text()
    assert ".user-dropdown:hover .dropdown-menu" not in css and ".user-dropdown:focus-within .dropdown-menu" not in css
