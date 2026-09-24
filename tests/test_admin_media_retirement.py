def test_retired_media_workspace_has_no_routes_or_endpoints(app, admin_client):
    rules = {rule.rule for rule in app.url_map.iter_rules()}

    assert not any(rule.startswith("/admin/media") for rule in rules)
    for path in (
        "/admin/media/dashboard",
        "/admin/media/view",
        "/admin/media/upload",
        "/admin/media/upload_multiple",
    ):
        assert admin_client.get(path).status_code == 404
