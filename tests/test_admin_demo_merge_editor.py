from pathlib import Path

from tests.conftest import _client_for_user


def _merge_url(seeded_data):
    return (
        "/admin/demo/merge?ids="
        f"{seeded_data['demo_id']},{seeded_data['pending_demo_id']}"
    )


def test_global_admin_merge_editor_uses_shared_form_contract(
    admin_client, seeded_data
):
    response = admin_client.get(_merge_url(seeded_data))

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'class="admin-page admin-workspace"' in page
    assert 'class="admin-form-section"' in page
    assert 'class="admin-check-row"' in page
    assert 'class="admin-disclosure"' in page
    assert 'class="admin-sticky-actions"' in page
    assert 'name="primary_demo_id"' in page
    assert 'name="recommendation_source"' in page
    assert 'name="field_source[title]"' in page


def test_restricted_admin_cannot_open_merge_editor(app, db, seeded_data):
    db.users.update_one(
        {"_id": seeded_data["user_id"]},
        {
            "$set": {
                "role": "admin",
                "global_admin": False,
                "global_permissions": ["EDIT_DEMO"],
            }
        },
    )
    client = _client_for_user(app, seeded_data["user_id"])

    response = client.get(_merge_url(seeded_data), follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/demo/")


def test_merge_editor_has_no_legacy_page_specific_ui_layer():
    template = Path(
        "mielenosoitukset_fi/templates/admin_V2/demonstrations/merge.html"
    ).read_text(encoding="utf-8")
    workspace = Path(
        "mielenosoitukset_fi/static/css/admin/workspace.css"
    ).read_text(encoding="utf-8")

    assert "admin-form admin-form-stack" in template
    assert "section.hidden = !manualEnabled" in template
    assert ".style.display" not in template
    assert 'class="row ' not in template
    assert 'class="col-' not in template
    assert 'class="table ' not in template
    assert "badge bg-" not in template
    assert "text-muted" not in template
    assert "accordion" not in template
    for legacy_selector in (
        ".admin-merge-form",
        ".demo-merge-card",
        ".merge-field-value",
        ".guided-plan-list",
        ".manual-mode-active",
    ):
        assert legacy_selector not in workspace
