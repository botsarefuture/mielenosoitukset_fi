from datetime import UTC, datetime

from mielenosoitukset_fi.utils.time_utils import utcnow


def test_utcnow_preserves_legacy_naive_utc_contract():
    before = datetime.now(UTC).replace(tzinfo=None)
    value = utcnow()
    after = datetime.now(UTC).replace(tzinfo=None)

    assert value.tzinfo is None
    assert before <= value <= after
