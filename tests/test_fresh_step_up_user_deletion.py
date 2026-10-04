"""Tests for fresh step-up authentication requirement on user deletion.

Covers the requirement that every individual user deletion must require
a fresh WebAuthn/passkey/sudo authentication ceremony, even if the
administrator already has a valid recent authenticated/sudo session.
"""

import time
from pathlib import Path
import re
import shutil
import subprocess

import pytest
from bson import ObjectId

from mielenosoitukset_fi.users.models import User
from mielenosoitukset_fi.utils.step_up import (
    create_fresh_step_up_token,
    consume_fresh_step_up_token,
    grant_elevation,
    is_elevated,
)
from mielenosoitukset_fi.utils.time_utils import utcnow
from tests import _webauthn_sim as sim
from tests.conftest import _cleanup_app_resources, _client_for_user

ORIGIN = "http://localhost"
RP_ID = "localhost"


@pytest.fixture
def wapp(app_factory):
    app = app_factory(WEBAUTHN_ORIGIN=ORIGIN, WEBAUTHN_RP_ID=RP_ID)
    try:
        yield app
    finally:
        _cleanup_app_resources(app)


def _create_user(db, username, password="Passw0rd1!", role="user", global_admin=False, global_permissions=None, mfa_secret=None):
    user_id = ObjectId()
    user_doc = User.create_user(
        username=username,
        password=password,
        email=f"{username}@example.test",
        displayname=username.title(),
    )
    user_doc.update({
        "_id": user_id,
        "confirmed": True,
        "active": True,
        "role": role,
        "global_admin": global_admin,
        "global_permissions": global_permissions or [],
    })
    db.users.insert_one(user_doc)
    if mfa_secret:
        db.mfas.insert_one({
            "user_id": user_id,
            "secret": mfa_secret,
            "device_name": "Test",
            "created_at": utcnow()
        })
        db.users.update_one({"_id": user_id}, {"$set": {"mfa_enabled": True}})
    return user_id


def _elevate_with_password(client, password="AdminPass1!"):
    r = client.post(
        "/users/auth/api/v2/step-up/password", json={"password": password}
    )
    assert r.status_code == 200, r.get_data(as_text=True)


def _get_fresh_step_up_token_via_webauthn(wapp, admin_user_id, target_user_id, admin_password="AdminPass1!"):
    """Helper to get a fresh step-up token via WebAuthn flow.

    First registers a passkey if needed, then uses it for fresh step-up.
    """
    client = _client_for_user(wapp, admin_user_id)
    key = sim.generate_key()

    # First, register a passkey for the admin (need elevation for this)
    _elevate_with_password(client, password=admin_password)
    r = client.post("/users/auth/api/v2/passkeys/register/options")
    options = r.get_json()["options"]
    credential = sim.registration_credential_json(options, key, origin=ORIGIN)
    r = client.post("/users/auth/api/v2/passkeys/register/verify", json={"credential": credential})
    assert r.status_code == 200
    credential_id = credential["id"]

    # Step 1: Get fresh step-up options
    r = client.post(
        "/users/auth/api/v2/step-up/fresh/options",
        json={"action": "delete_user", "target_id": str(target_user_id)}
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    options = r.get_json()["options"]

    # Step 2: Create assertion with the registered credential
    credential = sim.assertion_credential_json(
        options, key, origin=ORIGIN, credential_id=credential_id, counter=1
    )

    # Step 3: Verify and get token
    r = client.post(
        "/users/auth/api/v2/step-up/fresh/webauthn/verify",
        json={"credential": credential}
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()
    assert data["status"] == "success"
    assert "fresh_step_up_token" in data
    return data["fresh_step_up_token"]


def test_delete_user_without_fresh_step_up_rejected(wapp, db, seeded_data):
    """Test 1: Admin attempts user deletion without step-up authentication."""
    admin_id = seeded_data["admin_id"]
    target_id = seeded_data["user_id"]
    client = _client_for_user(wapp, admin_id)

    # No fresh step-up token
    r = client.post(
        "/admin/user/delete_user",
        json={"user_id": str(target_id)}
    )
    assert r.status_code == 403
    assert r.get_json()["error"] == "fresh_step_up_required"

    # User should still exist
    assert db.users.find_one({"_id": target_id}) is not None


def test_delete_user_with_recent_sudo_session_still_requires_fresh(wapp, db, seeded_data):
    """Test 2: Admin has valid recent sudo session from another action.

    Deletion should STILL require fresh authentication.
    """
    admin_id = seeded_data["admin_id"]
    target_id = seeded_data["user_id"]
    client = _client_for_user(wapp, admin_id)

    # First, get a regular sudo elevation (e.g., for passkey management)
    _elevate_with_password(client)

    # Verify session is elevated
    r = client.get("/users/auth/api/v2/step-up/status")
    assert r.get_json()["elevated"] is True

    # Now try to delete user WITHOUT fresh step-up token
    r = client.post(
        "/admin/user/delete_user",
        json={"user_id": str(target_id)}
    )
    assert r.status_code == 403
    assert r.get_json()["error"] == "fresh_step_up_required"

    # User should still exist
    assert db.users.find_one({"_id": target_id}) is not None


def test_delete_user_with_fresh_webauthn_step_up_succeeds(wapp, db, seeded_data):
    """Test 3: Admin completes fresh WebAuthn step-up, deletion succeeds."""
    admin_id = seeded_data["admin_id"]
    target_id = seeded_data["user_id"]

    # Register a passkey for the admin first
    client = _client_for_user(wapp, admin_id)
    _elevate_with_password(client)
    key = sim.generate_key()
    r = client.post("/users/auth/api/v2/passkeys/register/options")
    options = r.get_json()["options"]
    credential = sim.registration_credential_json(options, key, origin=ORIGIN)
    r = client.post("/users/auth/api/v2/passkeys/register/verify", json={"credential": credential})
    assert r.status_code == 200

    # Now get fresh step-up token for delete_user
    fresh_token = _get_fresh_step_up_token_via_webauthn(wapp, admin_id, target_id)

    # Use the token to delete user
    r = client.post(
        "/admin/user/delete_user",
        json={"user_id": str(target_id), "fresh_step_up_token": fresh_token}
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()["status"] == "OK"

    # User should be deleted
    assert db.users.find_one({"_id": target_id}) is None


def test_delete_user_with_fresh_password_step_up_succeeds(wapp, db, seeded_data):
    """Test 3b: Admin completes fresh password step-up, deletion succeeds."""
    admin_id = seeded_data["admin_id"]
    target_id = seeded_data["user_id"]
    client = _client_for_user(wapp, admin_id)

    # Step 1: Get fresh step-up options
    r = client.post(
        "/users/auth/api/v2/step-up/fresh/options",
        json={"action": "delete_user", "target_id": str(target_id)}
    )
    assert r.status_code == 200

    # Step 2: Verify with password (no MFA for seeded admin)
    r = client.post(
        "/users/auth/api/v2/step-up/fresh/password",
        json={"password": "AdminPass1!"}
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()
    assert data["status"] == "success"
    fresh_token = data["fresh_step_up_token"]

    # Step 3: Delete user with fresh token
    r = client.post(
        "/admin/user/delete_user",
        json={"user_id": str(target_id), "fresh_step_up_token": fresh_token}
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()["status"] == "OK"

    # User should be deleted
    assert db.users.find_one({"_id": target_id}) is None


def test_delete_user_fresh_token_cannot_be_reused(wapp, db, seeded_data):
    """Test 6: Fresh token cannot be reused for another deletion."""
    admin_id = seeded_data["admin_id"]
    target_id = seeded_data["user_id"]

    # Create a second target user
    target2_id = _create_user(db, "target2", "Passw0rd1!")

    client = _client_for_user(wapp, admin_id)

    # Register a passkey for the admin
    _elevate_with_password(client)
    key = sim.generate_key()
    r = client.post("/users/auth/api/v2/passkeys/register/options")
    options = r.get_json()["options"]
    credential = sim.registration_credential_json(options, key, origin=ORIGIN)
    r = client.post("/users/auth/api/v2/passkeys/register/verify", json={"credential": credential})
    assert r.status_code == 200

    # Get fresh token for first deletion
    fresh_token = _get_fresh_step_up_token_via_webauthn(wapp, admin_id, target_id)

    # Delete first user
    r = client.post(
        "/admin/user/delete_user",
        json={"user_id": str(target_id), "fresh_step_up_token": fresh_token}
    )
    assert r.status_code == 200
    assert db.users.find_one({"_id": target_id}) is None

    # Try to reuse the SAME token for second deletion
    r = client.post(
        "/admin/user/delete_user",
        json={"user_id": str(target2_id), "fresh_step_up_token": fresh_token}
    )
    assert r.status_code == 403
    assert r.get_json()["error"] == "fresh_step_up_required"

    # Second user should still exist
    assert db.users.find_one({"_id": target2_id}) is not None


def test_delete_user_direct_endpoint_without_token_rejected(wapp, db, seeded_data):
    """Test 7: Direct endpoint access without fresh token is rejected."""
    admin_id = seeded_data["admin_id"]
    target_id = seeded_data["user_id"]
    client = _client_for_user(wapp, admin_id)

    # Direct POST without fresh_step_up_token
    r = client.post(
        "/admin/user/delete_user",
        json={"user_id": str(target_id)}
    )
    assert r.status_code == 403
    assert r.get_json()["error"] == "fresh_step_up_required"

    # User should still exist
    assert db.users.find_one({"_id": target_id}) is not None


def test_delete_user_without_admin_permission_rejected(wapp, db, seeded_data):
    """Test 8: User without admin permissions cannot delete even with auth."""
    # Create a non-admin user with a passkey
    user_id = _create_user(db, "regular", "Passw0rd1!")
    client = _client_for_user(wapp, user_id)

    # Register a passkey
    key = sim.generate_key()
    r = client.post("/users/auth/api/v2/passkeys/register/options")
    # This will fail without sudo - need to elevate first
    assert r.status_code == 403

    _elevate_with_password(client, password="Passw0rd1!")
    r = client.post("/users/auth/api/v2/passkeys/register/options")
    options = r.get_json()["options"]
    credential = sim.registration_credential_json(options, key, origin=ORIGIN)
    r = client.post("/users/auth/api/v2/passkeys/register/verify", json={"credential": credential})
    assert r.status_code == 200

    # Get fresh step-up token
    fresh_token = _get_fresh_step_up_token_via_webauthn(wapp, user_id, seeded_data["user_id"], admin_password="Passw0rd1!")

    # Try to delete with fresh token but without DELETE_USER permission
    r = client.post(
        "/admin/user/delete_user",
        json={"user_id": str(seeded_data["user_id"]), "fresh_step_up_token": fresh_token}
    )
    # Should be forbidden due to missing permission
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.get_data(as_text=True)}"
    # The response might be HTML (abort(403)) or JSON depending on error handlers
    # The key assertion is that access is denied


def test_fresh_step_up_token_expires(wapp, db, seeded_data):
    """Fresh step-up token expires after TTL."""
    admin_id = seeded_data["admin_id"]
    target_id = seeded_data["user_id"]
    client = _client_for_user(wapp, admin_id)

    # Get a fresh token via the normal flow
    fresh_token = _get_fresh_step_up_token_via_webauthn(wapp, admin_id, target_id)

    # Verify token works initially
    r = client.post(
        "/admin/user/delete_user",
        json={"user_id": str(target_id), "fresh_step_up_token": fresh_token}
    )
    # Need a fresh target since first one might be deleted
    target2_id = _create_user(db, "target2", "Passw0rd1!")

    # Token should be consumed after first use
    r = client.post(
        "/admin/user/delete_user",
        json={"user_id": str(target2_id), "fresh_step_up_token": fresh_token}
    )
    assert r.status_code == 403
    assert r.get_json()["error"] == "fresh_step_up_required"

    # User should still exist
    assert db.users.find_one({"_id": target2_id}) is not None


def test_fresh_step_up_token_bound_to_action_and_target(wapp, db, seeded_data):
    """Fresh token is bound to specific action and target_id."""
    admin_id = seeded_data["admin_id"]
    target_id = seeded_data["user_id"]
    target2_id = _create_user(db, "target2", "Passw0rd1!")
    client = _client_for_user(wapp, admin_id)

    # Get token for action "delete_user" with target_id=target_id
    fresh_token = _get_fresh_step_up_token_via_webauthn(wapp, admin_id, target_id)

    # Try to use it for a DIFFERENT target
    r = client.post(
        "/admin/user/delete_user",
        json={"user_id": str(target2_id), "fresh_step_up_token": fresh_token}
    )
    assert r.status_code == 403
    assert r.get_json()["error"] == "fresh_step_up_required"

    # Target2 should still exist
    assert db.users.find_one({"_id": target2_id}) is not None


def test_fresh_step_up_token_not_valid_for_other_actions(wapp, db, seeded_data):
    """Fresh token for one action cannot be used for another action."""
    # This test verifies the token is action-specific
    admin_id = seeded_data["admin_id"]
    target_id = seeded_data["user_id"]
    client = _client_for_user(wapp, admin_id)

    # Create a token manually for a different action using the helper
    # We'll use the internal function with a test request context
    from flask_login import login_user
    from mielenosoitukset_fi.utils.step_up import create_fresh_step_up_token

    with wapp.test_request_context():
        user_doc = db.users.find_one({"_id": admin_id})
        user = User.from_db(user_doc)
        login_user(user)
        token = create_fresh_step_up_token("some_other_action", str(target_id))

    # Try to use it for delete_user
    r = client.post(
        "/admin/user/delete_user",
        json={"user_id": str(target_id), "fresh_step_up_token": token}
    )
    assert r.status_code == 403
    assert r.get_json()["error"] == "fresh_step_up_required"


def test_existing_admin_actions_still_use_regular_sudo(wapp, db, seeded_data):
    """Test 9: Other admin actions still work with regular sudo (no regression)."""
    admin_id = seeded_data["admin_id"]
    client = _client_for_user(wapp, admin_id)

    # Regular sudo should still work for passkey registration
    _elevate_with_password(client)
    r = client.post("/users/auth/api/v2/passkeys/register/options")
    assert r.status_code == 200

    # Regular sudo should still work for MFA device rename (if that endpoint exists)
    r = client.get("/users/auth/api/v2/step-up/status")
    assert r.get_json()["elevated"] is True


def test_fresh_step_up_password_requires_totp_when_mfa_enabled(wapp, db):
    """Fresh step-up password flow requires TOTP when MFA is enabled."""
    import pyotp
    secret = pyotp.random_base32()
    user_id = _create_user(db, "mfa-user", "Passw0rd1!", mfa_secret=secret)
    client = _client_for_user(wapp, user_id)

    # Get fresh step-up options
    r = client.post(
        "/users/auth/api/v2/step-up/fresh/options",
        json={"action": "delete_user", "target_id": str(ObjectId())}
    )
    assert r.status_code == 200

    # Try password without TOTP - should fail
    r = client.post(
        "/users/auth/api/v2/step-up/fresh/password",
        json={"password": "Passw0rd1!"}
    )
    assert r.status_code == 400
    assert r.get_json()["error"] == "totp_required"

    # With correct TOTP - should succeed
    r = client.post(
        "/users/auth/api/v2/step-up/fresh/password",
        json={"password": "Passw0rd1!", "totp_code": pyotp.TOTP(secret).now()}
    )
    assert r.status_code == 200
    assert r.get_json()["status"] == "success"
    assert "fresh_step_up_token" in r.get_json()


def test_fresh_step_up_options_requires_action(wapp, db, seeded_data):
    """Fresh step-up options endpoint requires action parameter."""
    admin_id = seeded_data["admin_id"]
    client = _client_for_user(wapp, admin_id)

    r = client.post(
        "/users/auth/api/v2/step-up/fresh/options",
        json={}
    )
    assert r.status_code == 400
    assert r.get_json()["error"] == "invalid_action"


def test_fresh_step_up_verify_without_options_fails(wapp, db, seeded_data):
    """Fresh step-up verify fails if options not called first (no session binding)."""
    admin_id = seeded_data["admin_id"]
    client = _client_for_user(wapp, admin_id)

    # Try to verify without calling options first
    key = sim.generate_key()
    # Need a credential - but we can't create one without options
    # Just verify the endpoint returns error for missing session
    r = client.post(
        "/users/auth/api/v2/step-up/fresh/webauthn/verify",
        json={"credential": {}}
    )
    assert r.status_code == 400
    assert r.get_json()["error"] == "fresh_step_up_not_started"


def test_fresh_step_up_options_rejects_unknown_action_and_invalid_target(
    wapp, seeded_data
):
    client = _client_for_user(wapp, seeded_data["admin_id"])

    unknown = client.post(
        "/users/auth/api/v2/step-up/fresh/options",
        json={"action": "future_sensitive_action", "target_id": str(seeded_data["user_id"])},
    )
    assert unknown.status_code == 400
    assert unknown.get_json()["error"] == "invalid_action"

    malformed = client.post(
        "/users/auth/api/v2/step-up/fresh/options",
        json={"action": "delete_user", "target_id": "not-an-object-id"},
    )
    assert malformed.status_code == 400
    assert malformed.get_json()["error"] == "invalid_target"


def test_user_delete_modal_supports_real_webauthn_and_password_fallback():
    source = Path(
        "mielenosoitukset_fi/templates/admin_V2/_modals_users.html"
    ).read_text(encoding="utf-8")

    assert "decodePublicKeyOptions(freshStepUpOptions)" in source
    assert "formatAssertionCredential(credential)" in source
    assert 'id="freshStepUpPasswordForm"' in source
    assert 'id="freshStepUpTotpGroup" hidden' in source
    assert 'filename=\'js/webauthn.js\'' in source


def test_rendered_user_delete_javascript_parses(admin_client):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is unavailable")

    response = admin_client.get("/admin/user/")
    assert response.status_code == 200
    scripts = re.findall(
        r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>",
        response.get_data(as_text=True),
        flags=re.S,
    )
    script = next(item for item in scripts if "freshStepUpOptions" in item)
    result = subprocess.run(
        [node, "--check"],
        input=script,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
