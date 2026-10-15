import re

import pytest
from flask import template_rendered


@pytest.mark.parametrize('locale', ['fi', 'en', 'sv'])
def test_anonymous_edit_token_renders_without_city_admin_navigation(app, seeded_data, locale):
    app.config.update(BABEL_PUBLIC_LOCALES=['fi', 'en', 'sv'])
    client = app.test_client()
    with client.session_transaction() as session:
        session['locale'] = locale
    observed = {}

    def capture(sender, template, context, **extra):
        if template.name == 'admin_V2/demonstrations/form.html':
            for key in ['edit_demo_with_token', 'can_approve_demo', 'can_generate_edit_link', 'show_demo_access_panel']:
                observed[key] = context.get(key)

    with template_rendered.connected_to(capture, app):
        response = client.get(
            f"/admin/demo/edit_demo_with_token/{seeded_data['edit_token']}"
        )

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Kaupunkiadminin näkymä" not in page
    assert re.search(r'<form\b[^>]*id="demo-form"', page)
    assert observed == {'edit_demo_with_token': True, 'can_approve_demo': False,
        'can_generate_edit_link': False, 'show_demo_access_panel': False}
    approval_inputs = re.findall(r'<input\b[^>]*name="approved"[^>]*>', page)
    # Keep the existing hidden payload contract, but never offer an editable
    # approval control; forged approval POSTs are checked in lifecycle tests.
    assert approval_inputs and all('type="hidden"' in control for control in approval_inputs)
    assert 'generate-edit-link-btn' not in page
    assert re.search(r'<input\b[^>]*name="csrf_token"', page)
    with client.session_transaction() as session:
        assert '_user_id' not in session
