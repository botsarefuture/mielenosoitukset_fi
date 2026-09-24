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
    workspace = Path(
        "mielenosoitukset_fi/static/css/admin/workspace.css"
    ).read_text(encoding="utf-8")
    users = Path("mielenosoitukset_fi/static/css/admin/users.css").read_text(
        encoding="utf-8"
    )

    strong = re.search(
        r"--admin-workspace-orange-strong: light-dark\((#[0-9a-f]+), (#[0-9a-f]+)\)",
        workspace,
    ).groups()
    soft = re.search(
        r"--admin-workspace-orange-soft: light-dark\((#[0-9a-f]+), (#[0-9a-f]+)\)",
        workspace,
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
