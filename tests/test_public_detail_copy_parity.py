"""The host's detail copy stays identical to the Flask shell's msgids.

Detail renders in the React host, so its strings live in the TypeScript catalog.
The Flask shell still supplies the same text to the island until that route is
hosted; this check keeps the two sources from drifting in the meantime.
"""

import re
from pathlib import Path

SHELL = Path("mielenosoitukset_fi/utils/react_detail.py")
CATALOG = Path("frontend/src/app/detail.ts")


def _shell_messages():
    source = SHELL.read_text(encoding="utf-8")
    assert "def detail_messages():" in source
    body = source.split("def detail_messages():", 1)[1].split("\ndef ", 1)[0]
    return dict(re.findall(r'"(\w+)": _\("([^"]*)"\)', body))


def _catalog_messages():
    source = CATALOG.read_text(encoding="utf-8")
    assert "const fi: DetailMessages = {" in source
    block = source.split("const fi: DetailMessages = {", 1)[1].split("\n};", 1)[0]
    return dict(re.findall(r"(\w+): '([^']*)'", block))


def test_host_detail_copy_matches_the_flask_shell():
    shell = _shell_messages()
    catalog = _catalog_messages()

    assert len(shell) > 40, "The shell message contract must stay populated"
    assert len(catalog) > 40, "The host catalog must stay populated"

    invented = sorted(set(catalog) - set(shell))
    assert not invented, f"Host catalog uses strings the shell does not define: {invented}"

    changed = {
        key: (catalog[key], shell[key])
        for key in catalog
        if catalog[key] != shell[key]
    }
    assert not changed, f"Host catalog diverged from the shell msgids: {changed}"


def test_host_declares_the_account_routes_the_detail_screen_posts_to():
    source = CATALOG.read_text(encoding="utf-8")

    for route in (
        "/api/analytics/track_view",
        "/api/demonstrations/__EVENT_ID__/like",
        "/api/demonstrations/__EVENT_ID__/unlike",
        "/api/demonstrations/__EVENT_ID__/attending",
        "/api/demonstrations/__EVENT_ID__/invite",
        "/demonstration/__EVENT_ID__/ics",
        "/subscribe_reminder/__EVENT_ID__",
        "/users/profile/api/friends_list/",
        "/api/follow/organization/__ORGANIZATION_ID__",
        "/api/unfollow/organization/__ORGANIZATION_ID__",
        "/api/follow/recurring/__EVENT_ID__",
        "/api/unfollow/recurring/__EVENT_ID__",
        "/report",
    ):
        assert route in source, f"Missing detail account route {route}"
