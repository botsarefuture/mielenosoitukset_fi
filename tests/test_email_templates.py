from jinja2 import Environment, FileSystemLoader


def test_settings_changed_email_template_renders():
    env = Environment(loader=FileSystemLoader("mielenosoitukset_fi/templates/emails"))
    template = env.get_template("auth/settings_changed.html")

    rendered = template.render(
        {
            "user_name": "Test User",
            "changed_fields": {
                "city": {"old": "Helsinki", "new": "Kouvola"},
                "language": {"old": None, "new": "fi"},
            },
        }
    )

    assert "Test User" in rendered
    assert "city" in rendered
    assert "Helsinki" in rendered
    assert "Kouvola" in rendered


def test_demo_cancellation_link_email_explains_verified_vs_reviewed_paths():
    env = Environment(loader=FileSystemLoader("mielenosoitukset_fi/templates/emails"))
    template = env.get_template("demo_cancellation_link.html")

    verified_rendered = template.render(
        {
            "title": "Climate March",
            "date": "2026-06-15",
            "city": "Helsinki",
            "cancellation_link": "https://example.test/cancel",
            "official_contact": True,
        }
    )
    assert "vahvistettu Mielenosoitukset.fi:ssä" in verified_rendered
    assert "tulee voimaan heti" in verified_rendered

    reviewed_rendered = template.render(
        {
            "title": "Climate March",
            "date": "2026-06-15",
            "city": "Helsinki",
            "cancellation_link": "https://example.test/cancel",
            "official_contact": False,
        }
    )
    assert "ohjautuu ensin Mielenosoitukset.fi:n ylläpidon käsiteltäväksi" in reviewed_rendered
    assert "vasta sen jälkeen, jos ylläpito hyväksyy pyynnön" in reviewed_rendered
