from mielenosoitukset_fi.basic_routes import ensure_audit_pagination_indexes


def _index_keys(collection):
    return {
        tuple((field, direction) for field, direction in spec["key"])
        for spec in collection.index_information().values()
    }


def test_audit_collections_index_the_deterministic_pagination_order(db):
    expected = (("timestamp", -1), ("_id", -1))
    ensure_audit_pagination_indexes(db)

    assert expected in _index_keys(db.admin_logs)
    assert expected in _index_keys(db.super_audit_logs)
    assert (("entity_type", 1), ("entity_id", 1), ("timestamp", -1), ("_id", -1)) in _index_keys(db.admin_logs)
