#!/usr/bin/env python3
"""Render the historical changelog with the pending change notes."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
HEADING = "## UNRELEASED\n"


def render(root: Path) -> str:
    history = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    if history.count(HEADING) != 1:
        raise ValueError("CHANGELOG.md must contain exactly one ## UNRELEASED heading")

    notes = []
    for path in sorted((root / "changelog.d").glob("*.md")):
        if path.name == "README.md":
            continue
        note = path.read_text(encoding="utf-8").strip()
        if not note.startswith("- "):
            raise ValueError(f"{path}: start each note file with a Markdown bullet")
        notes.append(note)

    if not notes:
        return history
    return history.replace(HEADING, HEADING + "\n" + "\n".join(notes) + "\n", 1)


if __name__ == "__main__":
    try:
        sys.stdout.write(render(ROOT))
    except (OSError, ValueError) as exc:
        print(f"Cannot render changelog: {exc}", file=sys.stderr)
        sys.exit(1)
