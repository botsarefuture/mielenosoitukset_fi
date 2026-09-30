"""Contracts for credential-management dialogs in public account settings."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SETTINGS_TEMPLATE = ROOT / "mielenosoitukset_fi/templates/users/auth/settings.html"


def test_credential_actions_use_shared_accessible_modals(user_client):
    response = user_client.get("/users/auth/settings")

    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert 'class="modal fade user-modal" id="credentialRenameModal"' in html
    assert 'class="modal-content user-form" id="credential-rename-form"' in html
    assert 'aria-describedby="credential-rename-error"' in html
    assert 'role="alert" aria-live="assertive" hidden' in html
    assert 'class="modal fade user-modal" id="credentialRemovalModal"' in html
    assert 'aria-describedby="credential-removal-message"' in html
    assert "bootstrap.Modal.getOrCreateInstance" in html
    assert "credentialRemovalMessage.textContent" in html
    assert "returnFocus.isConnected" in html


def test_settings_has_no_native_credential_dialogs_and_preserves_api_contracts():
    template = SETTINGS_TEMPLATE.read_text(encoding="utf-8")

    assert not re.search(r"\b(?:alert|confirm|prompt)\s*\(", template)
    assert 'fetchWithStepUp("/users/auth/api/v2/mfa_device_rename"' in template
    assert 'fetchWithStepUp("/users/auth/api/v2/mfa_device_revoke"' in template
    assert 'fetchWithStepUp("/users/auth/api/v2/passkeys/rename"' in template
    assert 'fetchWithStepUp("/users/auth/api/v2/passkeys/delete"' in template
    assert "JSON.stringify({ device_id: d.id, name: newName })" in template
    assert "JSON.stringify({ device_id: d.id })" in template
    assert "JSON.stringify({ id: pk.id, name: newName })" in template
    assert "JSON.stringify({ id: pk.id })" in template
    assert "if (!ok) return null;" in template
    assert template.count("if (!r) return;") >= 3
    assert template.count("if (!res) return;") >= 2


def test_rendered_settings_inline_javascript_parses(user_client):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not available")

    response = user_client.get("/users/auth/settings")
    scripts = re.findall(
        r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>",
        response.get_data(as_text=True),
        flags=re.S,
    )

    assert scripts
    for index, script in enumerate(scripts, start=1):
        result = subprocess.run(
            [node, "--check"],
            input=script,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, f"inline script {index}: {result.stderr}"


def test_credential_dialog_copy_is_translated_in_supported_catalogs():
    expected = {
        "fi": (
            'msgstr "Anna nimi ennen tallentamista."',
            'msgstr "Haluatko poistaa tämän laitteen?"',
        ),
        "en": (
            'msgstr "Enter a name before saving."',
            'msgstr "Do you want to remove this device?"',
        ),
        "sv": (
            'msgstr "Ange ett namn innan du sparar."',
            'msgstr "Vill du ta bort den här enheten?"',
        ),
    }

    for locale, translations in expected.items():
        catalog = (
            ROOT
            / "mielenosoitukset_fi"
            / "translations"
            / locale
            / "LC_MESSAGES"
            / "messages.po"
        ).read_text(encoding="utf-8")
        for translation in translations:
            assert translation in catalog
