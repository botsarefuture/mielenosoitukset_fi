from pymongo import UpdateOne

from mielenosoitukset_fi.utils.validators import normalize_email, normalize_username


def migrate_user_identity_uniqueness(db):
    """Backfill canonical identities and enforce case-insensitive uniqueness."""
    updates = []
    usernames = {}
    emails = {}

    for user in db.users.find({}, {"username": 1, "email": 1}):
        username = normalize_username(user.get("username"))
        email = normalize_email(user.get("email"))

        if username:
            if username in usernames:
                raise RuntimeError(f"Duplicate canonical username: {username}")
            usernames[username] = user["_id"]
        if email:
            if email in emails:
                raise RuntimeError(f"Duplicate canonical email: {email}")
            emails[email] = user["_id"]

        set_fields = {}
        unset_fields = {}
        if username:
            set_fields["username_canonical"] = username
        else:
            unset_fields["username_canonical"] = ""
        if email:
            set_fields["email_canonical"] = email
        else:
            unset_fields["email_canonical"] = ""

        update = {}
        if set_fields:
            update["$set"] = set_fields
        if unset_fields:
            update["$unset"] = unset_fields
        updates.append(UpdateOne({"_id": user["_id"]}, update))

    if updates:
        db.users.bulk_write(updates)

    db.users.create_index(
        "username_canonical",
        unique=True,
        sparse=True,
        name="users_username_canonical_unique",
    )
    db.users.create_index(
        "email_canonical",
        unique=True,
        sparse=True,
        name="users_email_canonical_unique",
    )
    return {
        "users_backfilled": len(updates),
        "unique_usernames": len(usernames),
        "unique_emails": len(emails),
    }
