"""Every Socket.IO client backs off with jitter so restarts don't cause a reconnect storm (#640)."""
import re
from pathlib import Path

CLIENTS = [
    Path("frontend/src/components/organization/ChatPanel.tsx"),
    Path("mielenosoitukset_fi/templates/users/profile/messages.html"),
]


def test_known_socketio_clients_use_jittered_backoff():
    for path in CLIENTS:
        source = path.read_text(encoding="utf-8")
        calls = re.findall(r"\bio\((\{[^)]*\})\)", source)
        assert calls, path
        for options in calls:
            assert "reconnectionDelay: 2000" in options, path
            assert "reconnectionDelayMax: 60000" in options, path
            assert "randomizationFactor: 0.5" in options, path


def test_no_other_socketio_clients_use_defaults():
    roots = [Path("frontend/src"), Path("mielenosoitukset_fi/templates"), Path("mielenosoitukset_fi/static/js")]
    offenders = []
    for root in roots:
        for path in root.rglob("*"):
            if path.suffix not in {".ts", ".tsx", ".js", ".html"} or ".min." in path.name:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for options in re.findall(r"\bio\((\{[^)]*\})?\)", text):
                if "reconnectionDelayMax" not in options:
                    offenders.append(str(path))
    assert offenders == []
