from pathlib import Path


DETAIL = Path("mielenosoitukset_fi/templates/detail.html")


def test_detail_invite_dialog_uses_safe_dom_rendering_and_app_feedback():
    source = DETAIL.read_text(encoding="utf-8")

    assert 'id="invite-friends-status"' in source
    assert 'aria-live="polite"' in source
    assert 'friendsList.replaceChildren()' in source
    assert 'document.createTextNode(friend.displayname || "")' in source
    assert 'label.appendChild(avatar)' in source
    assert 'displayFlashMessage("success"' in source
    assert 'sendInviteBtn.disabled = true' in source
    assert 'const payload = await response.json().catch(() => null);' in source
    assert 'payload.error' in source
    assert 'alert("Kutsut lähetetty! 💌")' not in source
    assert 'div.innerHTML = `' not in source[source.index("function openInviteDialog"):source.index("</script>", source.index("function openInviteDialog"))]


def test_detail_invite_dialog_has_translated_visible_copy():
    source = DETAIL.read_text(encoding="utf-8")

    for text in (
        "Kutsu kavereita osallistumaan",
        "Valitse kaverit, jotka haluat kutsua tähän mielenosoitukseen:",
        "Lähetä kutsut",
        "Kirjaudu sisään",
    ):
        assert f"{{{{ _('{text}') }}}}" in source
