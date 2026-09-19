"""Contracts for consistent admin flash-message source language and extraction."""

import ast
from io import BytesIO
from pathlib import Path

from babel.messages.extract import extract_python


ADMIN_BP = Path("mielenosoitukset_fi/admin/admin_bp.py")
ADMIN_MODULES = tuple(Path("mielenosoitukset_fi/admin").glob("*.py"))


def _literal_flash_messages(path: Path):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    return {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "flash_message"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }


def test_admin_flash_messages_do_not_mix_known_english_source_copy():
    messages = _literal_flash_messages(ADMIN_BP)
    removed_english_messages = {
        "Panic mode activated!",
        "Panic mode deactivated!",
        "This job cannot be run manually.",
        "Job queued to run now.",
        "Schedule updated.",
        "An error occurred while loading statistics.",
    }

    assert messages.isdisjoint(removed_english_messages)
    assert "Hätätila otettiin käyttöön." in messages
    assert "Tilastojen lataaminen epäonnistui." in messages


def test_babel_extracts_flash_message_first_arguments():
    extracted = set()
    for _line, function_name, messages, _comments in extract_python(
        BytesIO(ADMIN_BP.read_bytes()),
        keywords={"flash_message": (1,)},
        comment_tags=(),
        options={},
    ):
        if function_name != "flash_message":
            continue
        if isinstance(messages, tuple):
            extracted.update(message for message in messages if message)
        elif messages:
            extracted.add(messages)

    assert "Hätätila otettiin käyttöön." in extracted
    assert "Taustatyön ajastuksen päivitys epäonnistui: %(error)s" in extracted


def test_admin_flash_messages_do_not_use_unextractable_f_strings():
    violations = []
    for path in ADMIN_MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "flash_message"
                and node.args
                and isinstance(node.args[0], ast.JoinedStr)
            ):
                violations.append(f"{path}:{node.lineno}")

    assert violations == []


def test_repository_extraction_command_includes_flash_messages():
    script = Path("scripts/extract_translations.sh").read_text(encoding="utf-8")
    docs = Path("TRANSLATING.md").read_text(encoding="utf-8")

    assert "-k flash_message:1" in script
    assert "./scripts/extract_translations.sh" in docs
    assert "pybabel extract -F babel.cfg -o messages.pot ." not in docs
