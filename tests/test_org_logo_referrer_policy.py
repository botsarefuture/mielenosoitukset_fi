from pathlib import Path


TEMPLATE_ROOT = Path("mielenosoitukset_fi/templates")
ORGANIZATION_LOGO_TEMPLATES = (
    "admin_V2/organizations/form.html",
    "detail.html",
    "organizations/details.html",
    "users/profile/profile.html",
    "users/profile/profile copy.html",
)


def test_organization_logo_images_do_not_send_preview_referrers():
    for relative_path in ORGANIZATION_LOGO_TEMPLATES:
        template = (TEMPLATE_ROOT / relative_path).read_text()
        logo_lines = [
            line
            for line in template.splitlines()
            if "<img" in line and ("org.logo" in line or "organization.logo" in line)
        ]

        assert logo_lines, f"No organization logo image found in {relative_path}"
        assert all('referrerpolicy="no-referrer"' in line for line in logo_lines)
