"""Read-only auth bridge scopes of /api/session (docs/auth-bridge.md).

The scopes are off by default; with the flag off the endpoint must behave
exactly as before, so a rollback is one configuration change.
"""

import pytest


@pytest.fixture
def bridge_on(app):
    app.config["AUTH_BRIDGE_SCOPES"] = True
    yield
    app.config["AUTH_BRIDGE_SCOPES"] = False


def _org(seeded_data):
    return str(seeded_data["org_id"])


def test_flag_is_off_by_default(app):
    assert app.config.get("AUTH_BRIDGE_SCOPES", False) is False


def test_flag_off_ignores_new_scopes(client, user_client, seeded_data):
    org = _org(seeded_data)
    with client.session_transaction() as s:
        s["_flashes"] = [("success", "Kiitos")]
    anonymous = client.get(f"/api/session?organization_id={org}&permission=EDIT_DEMO").get_json()
    assert "organization" not in anonymous and "permissions" not in anonymous
    signed_in = user_client.get("/api/session?permission=EDIT_DEMO").get_json()
    assert "permissions" not in signed_in


def test_anonymous_flash_flag_for_organization(client, seeded_data, bridge_on):
    org = _org(seeded_data)
    body = client.get(f"/api/session?organization_id={org}").get_json()
    assert body["organization"] == {"id": org, "has_messages": False}
    with client.session_transaction() as s:
        s["_flashes"] = [("success", "Kiitos")]
    body = client.get(f"/api/session?organization_id={org}").get_json()
    assert body["organization"] == {"id": org, "has_messages": True}
    assert body["authenticated"] is False
    # Reading the flag never consumes the message.
    assert client.get("/get_flash_messages").get_json()["messages"]


def test_anonymous_gets_no_invitation_or_permission_data(client, seeded_data, bridge_on):
    body = client.get(f"/api/session?organization_id={_org(seeded_data)}&permission=EDIT_ORGANIZATION").get_json()
    assert set(body["organization"]) == {"id", "has_messages"}
    assert body["permissions"] == {"EDIT_ORGANIZATION": False}


def test_permission_scope_is_bounded_and_boolean(user_client, bridge_on):
    query = "&".join(["permission=EDIT_DEMO", "permission=lower", "permission=EDIT_DEMO", "permission=X%20Y"]
                     + [f"permission=PERM_{i}" for i in range(20)])
    body = user_client.get("/api/session?" + query).get_json()
    assert len(body["permissions"]) == 10
    assert "lower" not in body["permissions"] and "X Y" not in body["permissions"]
    assert all(isinstance(v, bool) for v in body["permissions"].values())


def test_permission_scope_matches_has_permission(user_client, db, seeded_data, bridge_on):
    org = _org(seeded_data)
    body = user_client.get(f"/api/session?organization_id={org}&permission=EDIT_ORGANIZATION&permission=DELETE_ORGANIZATION").get_json()
    assert body["permissions"] == {"EDIT_ORGANIZATION": True, "DELETE_ORGANIZATION": False}
    assert body["organization"]["permissions"]["EDIT_ORGANIZATION"] is True


def test_responses_stay_uncacheable(client, seeded_data, bridge_on):
    response = client.get(f"/api/session?organization_id={_org(seeded_data)}&permission=EDIT_DEMO")
    assert response.headers["Cache-Control"] == "no-store"
    assert "Cookie" in response.headers["Vary"]


def test_marker_tells_react_the_bridge_is_on(client, seeded_data, bridge_on):
    assert client.get("/api/session").get_json()["auth_bridge"] is True


def test_marker_absent_when_flag_off(client):
    assert "auth_bridge" not in client.get("/api/session").get_json()
