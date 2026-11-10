import json
import re
import subprocess
import sys
from pathlib import Path

import markdown


def test_public_shell_has_language_and_semantic_footer_lists(client):
    response = client.get("/submit")

    assert response.status_code == 200
    page = response.get_data(as_text=True)

    assert re.search(r"<html lang=\"[^\"]+\"", page)
    assert '<footer class="footer public-site-footer">' in page
    assert '<nav aria-label="Sivuston alatunniste">' in page
    assert 'class="footer-links auth-buttons public-site-footer__auth"' in page
    assert 'class="footer-separator"' not in page
    assert 'style="color: var(--secondary_color);"' not in page
    assert '<div class="auth-buttons">' not in page


def test_city_today_page_has_a_document_language(client):
    with client.session_transaction() as session:
        session["locale"] = ""

    response = client.get("/city/rovaniemi/tanaan")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert '<html lang="fi"' in page


def test_public_chat_feedback_uses_safe_shared_toast():
    messages = Path("mielenosoitukset_fi/templates/users/profile/messages.html").read_text(
        encoding="utf-8"
    )
    toaster = Path("mielenosoitukset_fi/static/js/toaster.js").read_text(encoding="utf-8")

    assert "js/toaster.js" in messages
    assert "showToast(" in messages
    assert "alert(" not in messages
    assert "text.textContent = String(message" in toaster
    assert "innerHTML" not in toaster
    assert "role', 'status'" in toaster
    assert "aria-live', 'polite'" in toaster


def test_api_documentation_code_blocks_are_focusable_and_links_are_distinct(client):
    response = client.get("/api-docs/")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    workspace = Path("mielenosoitukset_fi/static/css/user-workspace.css").read_text(
        encoding="utf-8"
    )

    assert '<pre tabindex="0">' in page
    assert ".api-docs-content pre:focus-visible" in workspace
    assert ".api-docs-content a" in workspace
    assert "text-decoration: underline" in workspace
    assert "var(--product-primary)" in workspace


def test_api_documentation_build_preserves_flask_markdown():
    document = markdown.Markdown(
        extensions=["fenced_code", "tables", "toc"],
        extension_configs={"toc": {"permalink": True}},
    )
    expected = document.convert(Path("docs/api.md").read_text(encoding="utf-8"))
    expected = expected.replace("<pre>", '<pre tabindex="0">')
    compiled = json.loads(subprocess.check_output(
        [sys.executable, "frontend/render-api-docs.py"], text=True
    ))
    unwrapped = compiled["html"].replace(
        '<div class="api-docs-table" tabindex="0" role="region" '
        'aria-label="API-dokumentaatio"><table>', "<table>"
    ).replace("</table></div>", "</table>")

    assert unwrapped == expected
    assert compiled["toc"] == document.toc
    assert len(re.findall(r'<pre tabindex="0">', compiled["html"])) > 0
    assert '<table>' in compiled["html"]


def test_api_documentation_slashless_redirect_preserves_query(client):
    response = client.get("/api-docs?lang=fi&source=test")

    assert response.status_code == 308
    assert response.headers["Location"].endswith("/api-docs/?lang=fi&source=test")
