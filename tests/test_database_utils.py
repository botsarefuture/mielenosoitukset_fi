import unittest
from datetime import datetime

from bson import ObjectId

from mielenosoitukset_fi.utils.database import (
    finnish_to_iso,
    iso_to_finnish,
    revert_stringified_object_ids,
    stringify_object_ids,
)


class User:
    def __init__(self):
        self.to_dict_calls = []

    def to_dict(self, include_private):
        self.to_dict_calls.append(include_private)
        return {"id": "user-1", "include_private": include_private}


class DatabaseUtilsTests(unittest.TestCase):
    def test_stringify_object_ids_converts_nested_ids_and_dates(self):
        nested_id = ObjectId()
        payload = {
            "id": nested_id,
            "date": datetime(2026, 3, 23, 9, 15),
            "items": [{"nested_id": nested_id}],
        }

        result = stringify_object_ids(payload)

        self.assertEqual(
            result,
            {
                "id": str(nested_id),
                "date": "2026-03-23",
                "items": [{"nested_id": str(nested_id)}],
            },
        )

    def test_stringify_object_ids_uses_to_dict_for_user_objects(self):
        user = User()

        result = stringify_object_ids(user)

        self.assertEqual(
            result,
            {"id": "user-1", "include_private": True},
        )
        self.assertEqual(user.to_dict_calls, [True])

    def test_revert_stringified_object_ids_restores_nested_values(self):
        object_id = ObjectId()
        payload = {
            "id": str(object_id),
            "date": "2026-03-23",
            "items": [{"value": "plain-string"}],
        }

        result = revert_stringified_object_ids(payload)

        self.assertEqual(result["id"], object_id)
        self.assertEqual(result["date"], datetime(2026, 3, 23))
        self.assertEqual(result["items"][0]["value"], "plain-string")

    def test_date_helpers_round_trip_between_finnish_and_iso(self):
        finnish_date = "23.03.2026"

        iso_date = finnish_to_iso(finnish_date)

        self.assertEqual(iso_date, "2026-03-23")
        self.assertEqual(iso_to_finnish(iso_date), finnish_date)


if __name__ == "__main__":
    unittest.main()
