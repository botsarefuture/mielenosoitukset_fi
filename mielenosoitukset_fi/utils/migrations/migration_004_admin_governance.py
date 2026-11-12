def migrate_admin_governance(db):
    """Prepare persistent governance storage and preserve city-manager access."""
    db.board_clearances.create_index("user_id", unique=True)
    db.board_audit_logs.create_index("timestamp", background=True)

    permission_result = db.users.update_many(
        {
            "global_permissions": {
                "$all": ["EDIT_USER"],
                "$nin": ["MANAGE_CITIES"],
            },
        },
        {"$addToSet": {"global_permissions": "MANAGE_CITIES"}},
    )
    return {"city_permissions_added": permission_result.modified_count}
