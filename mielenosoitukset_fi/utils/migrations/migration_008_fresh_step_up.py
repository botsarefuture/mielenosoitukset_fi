"""Migration: add storage/indexes for fresh step-up tokens."""

def migrate_fresh_step_up_storage(db):
    """Ensure the fresh_step_up_tokens collection exists with its indexes."""
    db.fresh_step_up_tokens.create_index(
        "expires_at", expireAfterSeconds=0, name="fresh_step_up_ttl"
    )
    db.fresh_step_up_tokens.create_index(
        [("user_id", 1), ("action", 1), ("used", 1)], name="fresh_step_up_lookup"
    )
    return {
        "fresh_step_up_tokens_indexes": sorted(db.fresh_step_up_tokens.index_information()),
    }