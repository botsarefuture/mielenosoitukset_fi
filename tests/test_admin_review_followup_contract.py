import re
from pathlib import Path


def _relative_luminance(color):
    channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92
        if channel <= 0.04045
        else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(first, second):
    lighter, darker = sorted(
        (_relative_luminance(first), _relative_luminance(second)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


def test_warning_foregrounds_meet_normal_text_contrast_in_both_themes():
    product_tokens = Path(
        "mielenosoitukset_fi/static/css/product-tokens.css"
    ).read_text(encoding="utf-8")
    users = Path("mielenosoitukset_fi/static/css/admin/users.css").read_text(
        encoding="utf-8"
    )

    strong = re.search(
        r"--product-accent-strong: light-dark\((#[0-9a-f]+), (#[0-9a-f]+)\)",
        product_tokens,
    ).groups()
    soft = re.search(
        r"--product-accent-soft: light-dark\((#[0-9a-f]+), (#[0-9a-f]+)\)",
        product_tokens,
    ).groups()
    assert all(_contrast(foreground, background) >= 4.5 for foreground, background in zip(strong, soft))
    assert not re.search(
        r"(?m)^\s*color: var\(--admin-workspace-orange\);$", users
    )


def test_demo_review_regressions_keep_shared_interaction_contracts():
    dashboard = Path(
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/dashboard.html"
    ).read_text(encoding="utf-8")

    assert dashboard.count(
        "admin-page-hero__action admin-page-hero__action--disabled"
    ) == 2
    assert "admin-data-view admin-data-view--scrollable" in dashboard
    assert "prefers-reduced-motion: reduce" in dashboard
    assert "window.setTimeout(removeRow, 350)" in dashboard
    freeze_modal = dashboard.split('id="freezeModal"', 1)[1].split("</div>", 4)[0]
    assert "btn-close-white" not in freeze_modal


def test_pride_badge_uses_contrasting_solid_product_surface():
    tokens = Path("mielenosoitukset_fi/static/css/product-tokens.css").read_text()
    foregrounds = re.search(
        r"--product-text: light-dark\((#[0-9a-f]+), (#[0-9a-f]+)\)", tokens
    ).groups()
    backgrounds = re.search(
        r"--product-surface: light-dark\((#[0-9a-f]+), (#[0-9a-f]+)\)", tokens
    ).groups()
    assert all(_contrast(text, surface) >= 4.5 for text, surface in zip(foregrounds, backgrounds))
    for filename in ("user-workspace.css", "v2/list.css"):
        css = Path(f"mielenosoitukset_fi/static/css/{filename}").read_text()
        badge = re.search(r"\.pride-badge\s*\{([^}]+)\}", css).group(1)
        assert "color: var(--product-text)" in badge
        assert "linear-gradient(var(--product-surface), var(--product-surface)) padding-box" in badge
        assert "var(--product-pride-gradient) border-box" in badge


def test_table_dropdowns_use_fixed_popper_without_mobile_override():
    script = Path("mielenosoitukset_fi/static/js/admin_workspace.js").read_text()
    assert '.admin-data-view__viewport [data-bs-toggle="dropdown"]' in script
    assert 'setAttribute("data-bs-boundary", "viewport")' in script
    assert '"strategy":"fixed"' in script
    # Bootstrap's delegated handlers capture on document; ours must run first,
    # and must also cover tables replaced after load (user list search/paging).
    assert 'window.addEventListener("click", useFixedTableDropdown, true)' in script
    css = Path("mielenosoitukset_fi/static/css/admin/workspace.css").read_text()
    assert ".admin-data-view__table .dropdown-menu.show" not in css
    assert "overflow-x: auto" in css
