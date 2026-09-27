from pathlib import Path


FOLLOW_TEMPLATES = (
    Path("mielenosoitukset_fi/templates/detail.html"),
    Path("mielenosoitukset_fi/templates/siblings.html"),
    Path("mielenosoitukset_fi/templates/organizations/details.html"),
)


def test_public_follow_failures_use_shared_safe_feedback():
    for template in FOLLOW_TEMPLATES:
        source = template.read_text(encoding="utf-8")

        assert "Seurannan päivittäminen epäonnistui" in source
        assert 'displayFlashMessage(' in source
        assert "|tojson" in source
        assert "alert(" not in source
