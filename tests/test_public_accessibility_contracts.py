import re


def test_public_shell_has_language_and_semantic_footer_lists(client):
    response = client.get("/submit")

    assert response.status_code == 200
    page = response.get_data(as_text=True)

    assert re.search(r"<html lang=\"[^\"]+\"", page)
    assert '<ul class="footer-links auth-buttons">' in page
    assert '<li class="footer-separator" aria-hidden="true">|</li>' in page
    assert '<div class="auth-buttons">' not in page


def test_city_today_page_has_a_document_language(client):
    with client.session_transaction() as session:
        session["locale"] = ""

    response = client.get("/city/rovaniemi/tanaan")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert '<html lang="fi"' in page


def test_api_documentation_code_blocks_are_focusable_and_links_are_distinct(client):
    response = client.get("/api-docs/")

    assert response.status_code == 200
    page = response.get_data(as_text=True)

    assert '<pre tabindex="0">' in page
    assert ".api-docs-content pre:focus-visible" in page
    assert ".api-docs-meta a" in page
    assert "text-decoration: underline" in page
    assert "--api-docs-link: #0056b3" in page
