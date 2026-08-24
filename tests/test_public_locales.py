from flask import render_template
from flask_babel import get_locale


def test_unpublished_language_cannot_be_selected(app, client):
    app.config.update(
        BABEL_SUPPORTED_LOCALES=["fi", "en"],
        BABEL_PUBLIC_LOCALES=["fi"],
    )

    response = client.get("/set_language/en")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    with client.session_transaction() as session:
        assert session.get("locale") != "en"


def test_stale_unpublished_locale_is_removed(app, client):
    app.config.update(
        BABEL_SUPPORTED_LOCALES=["fi", "en"],
        BABEL_PUBLIC_LOCALES=["fi"],
    )
    with client.session_transaction() as session:
        session["locale"] = "en"

    response = client.get("/")

    assert response.status_code == 200
    with client.session_transaction() as session:
        assert "locale" not in session


def test_browser_language_cannot_enable_unpublished_locale(app, client):
    app.config.update(
        BABEL_SUPPORTED_LOCALES=["fi", "en"],
        BABEL_PUBLIC_LOCALES=["fi"],
    )

    app.add_url_rule(
        "/_test/locale",
        endpoint="test_selected_locale",
        view_func=lambda: str(get_locale()),
    )

    response = client.get("/_test/locale", headers={"Accept-Language": "en"})

    assert response.status_code == 200
    assert response.data == b"fi"


def test_single_public_language_hides_selector(app, client):
    app.config.update(
        BABEL_SUPPORTED_LOCALES=["fi", "en"],
        BABEL_PUBLIC_LOCALES=["fi"],
    )

    response = client.get("/")

    assert response.status_code == 200
    assert b'class="language-buttons"' not in response.data


def test_sitemap_does_not_advertise_unpublished_language(app, client):
    app.config.update(
        BABEL_SUPPORTED_LOCALES=["fi", "en"],
        BABEL_PUBLIC_LOCALES=["fi"],
    )

    response = client.get("/sitemap.xml")

    assert response.status_code == 200
    assert b'hreflang="en"' not in response.data


def test_maintenance_page_hides_unpublished_english(app):
    app.config.update(
        BABEL_SUPPORTED_LOCALES=["fi", "en"],
        BABEL_PUBLIC_LOCALES=["fi"],
    )

    with app.test_request_context("/"):
        page = render_template("heavy.html")

    assert "Switch to English" not in page
    assert "Service temporarily unavailable" not in page


def test_submission_pages_offer_translation_help(client):
    for path in ("/submit", "/ohjeet/"):
        response = client.get(path)

        assert response.status_code == 200
        assert "Jos tarvitset käännösapua" in response.get_data(as_text=True)
        assert 'href="mailto:tuki@mielenosoitukset.fi"' in response.get_data(
            as_text=True
        )
