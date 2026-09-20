"""Migration: add storage/indexes for WebAuthn passkeys."""


def migrate_passkey_storage(db):
    """Ensure the passkey and challenge collections exist with their indexes."""
    db.user_passkeys.create_index(
        "credential_id",
        unique=True,
        name="user_passkeys_credential_id_unique",
    )
    db.user_passkeys.create_index(
        "user_id",
        name="user_passkeys_user_id",
    )
    db.passkey_challenges.create_index(
        "expires_at",
        name="passkey_challenges_expires_at",
    )
    db.passkey_challenges.create_index(
        [("purpose", 1), ("session_token", 1), ("used", 1)],
        name="passkey_challenges_consumption",
    )
    return {
        "user_passkeys_indexes": sorted(db.user_passkeys.index_information()),
        "passkey_challenges_indexes": sorted(db.passkey_challenges.index_information()),
    }