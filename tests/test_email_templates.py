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
