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


def _city_assignment_context():
    return {
        "title": "Climate March",
        "date": "2026-06-15",
        "city": "Helsinki",
        "address": "Mannerheimintie 1",
        "submitter_name": "Test Ilmoittaja",
        "submitter_email": "ilmoittaja@example.test",
        "submitter_role": "organizer",
        "approve_link": "https://example.test/approve",
        "preview_link": "https://example.test/preview",
        "reject_link": "https://example.test/reject",
        "escalate_after_hours": 24,
    }


def test_city_assignment_email_template_renders():
    env = Environment(loader=FileSystemLoader("mielenosoitukset_fi/templates/emails"))
    template = env.get_template("admin_demo_city_assignment.html")

    rendered = template.render(_city_assignment_context())

    assert "Uusi mielenosoitus odottaa käsittelyä" in rendered
    assert "Climate March" in rendered
    assert "Mielenosoitusta ei käsitellä kansallisessa tiimissä automaattisesti" in rendered
    assert "Hyväksy mielenosoitus" in rendered
    assert "https://example.test/approve" in rendered
    assert "24 tunnin kuluessa" in rendered


def test_city_assignment_escalation_email_template_renders():
    env = Environment(loader=FileSystemLoader("mielenosoitukset_fi/templates/emails"))
    template = env.get_template("admin_demo_city_escalation.html")

    rendered = template.render(_city_assignment_context())

    assert "Mielenosoitus nousi kansalliselle tasolle" in rendered
    assert "Climate March" in rendered
    assert "siirtynyt kaupungin ylläpidosta kansallisen tiimin käsiteltäväksi" in rendered
    assert "Hyväksy mielenosoitus" in rendered
    assert "https://example.test/reject" in rendered
