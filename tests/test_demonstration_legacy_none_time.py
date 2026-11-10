from mielenosoitukset_fi.utils.classes.Demonstration import Demonstration, is_none


def test_literal_none_text_is_empty():
    assert is_none("None") and is_none(" null ") and is_none("")
    assert not is_none("10:00")


def test_literal_none_time_converts_to_none():
    assert Demonstration._to_iso8601_time(None, "None") is None
    assert Demonstration._to_iso8601_time(None, "10:30") == "10:30:00"
