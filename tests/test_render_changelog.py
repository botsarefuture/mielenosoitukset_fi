from pathlib import Path

import pytest

from scripts.render_changelog import ROOT, render


def test_repository_change_notes_render():
    # Run the same validation contributors use against every committed note.
    assert render(ROOT).startswith("# Changelog\n")


def test_render_preserves_history_and_orders_notes(tmp_path: Path):
    history = "# Changelog\n\n## UNRELEASED\n\n- Existing entry.\n\n## v1\n\n- Old entry.\n"
    (tmp_path / "CHANGELOG.md").write_text(history, encoding="utf-8")
    notes = tmp_path / "changelog.d"
    notes.mkdir()
    (notes / "README.md").write_text("Instructions", encoding="utf-8")
    (notes / "b.md").write_text("- Second.\n", encoding="utf-8")
    (notes / "a.md").write_text("- First.\n", encoding="utf-8")

    result = render(tmp_path)

    assert result == history.replace("## UNRELEASED\n", "## UNRELEASED\n\n- First.\n- Second.\n")
    assert (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8") == history
    assert render(tmp_path) == result


def test_invalid_note_does_not_return_a_partial_changelog(tmp_path: Path):
    (tmp_path / "CHANGELOG.md").write_text("## UNRELEASED\n", encoding="utf-8")
    (tmp_path / "changelog.d").mkdir()
    (tmp_path / "changelog.d" / "bad.md").write_text("Not a bullet", encoding="utf-8")

    with pytest.raises(ValueError, match="Markdown bullet"):
        render(tmp_path)
