from urllib.parse import urlparse

CANONICAL_SITEMAP_URL = "https://mielenosoitukset.fi/sitemap.xml"
SITEMAP_LINE = f"Sitemap: {CANONICAL_SITEMAP_URL}"

EXISTING_DIRECTIVES = [
    "User-agent: *",
    "Disallow: /admin/",
    "Disallow: /users/auth/login/",
    "Disallow: /users/auth/register/",
    "Disallow: /users/auth/forgot/",
]


def _production_robots(app):
    response = app.test_client().get(
        "/robots.txt", base_url="https://mielenosoitukset.fi"
    )
    assert response.status_code == 200
    assert response.mimetype == "text/plain"
    return response.get_data(as_text=True)


def test_robots_txt_advertises_canonical_sitemap(app):
    body = _production_robots(app)

    assert SITEMAP_LINE in body
    assert "sitemap.xml?" not in body


def test_robots_txt_keeps_existing_directives_and_single_sitemap(app):
    body = _production_robots(app)
    lines = [line.strip() for line in body.splitlines() if line.strip()]

    for directive in EXISTING_DIRECTIVES:
        assert directive in lines

    sitemap_lines = [line for line in lines if line.lower().startswith("sitemap:")]
    assert sitemap_lines == [SITEMAP_LINE]

    for line in lines:
        assert line == SITEMAP_LINE or any(
            line.lower().startswith(prefix)
            for prefix in ("user-agent:", "disallow:")
        )

    parsed = urlparse(sitemap_lines[0].split(":", 1)[1].strip())
    assert parsed.scheme == "https"
    assert parsed.netloc == "mielenosoitukset.fi"
    assert parsed.path == "/sitemap.xml"
    assert parsed.query == ""
    assert parsed.fragment == ""
