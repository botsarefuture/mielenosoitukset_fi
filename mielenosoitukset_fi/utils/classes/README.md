Perfect! ✨ I’ll extend your spec with the **class-building guidelines** so it’s consistent and implementation-ready.

---

# SPEC

## Terms

* **OID**: `ObjectId`

  * Used as the standard type for unique identifiers.
  * Always stored in MongoDB as `ObjectId`.

---

## Processing Saves

* All documents must include an `_id` field of type `OID`.
* Saves should ensure:

  * If `_id` is missing → generate new `ObjectId`.
  * If `_id` is provided → validate that it is a valid `ObjectId`.
* Updates should never overwrite `_id`.

---

## Referencing Other Types

### By `_id`

* References between documents must always be stored as `OID`.
* Example:

  ```json
  {
    "_id": ObjectId("64f15a3c2b5f4c8a9f1b1234"),
    "user_id": ObjectId("64f15b4c2b5f4c8a9f1b5678"),
    "event_id": ObjectId("64f15c7c2b5f4c8a9f1b9abc")
  }
  ```
* No stringified ObjectIds allowed.

---

## How to Build Classes

Each MongoDB-backed class should follow a consistent interface.

### Necessary Functions

* **`to_dict(self) -> dict`**

  * Converts the class instance into a MongoDB-compatible dictionary.
  * Ensures all `ObjectId` fields are stored as `ObjectId`.

* **`from_dict(cls, data: dict) -> "ClassName"`**

  * Class method to construct an object instance from a MongoDB dictionary.

* **`_from_id(cls, oid: OID) -> "ClassName"`**

  * Class method to load a single object from MongoDB by `_id`.
  * Must raise an error or return `None` if not found.

* **`save(self)`**

  * Inserts or updates the document in MongoDB.
  * If `_id` is not set, generate a new `ObjectId`.
  * If `_id` exists, perform an update instead of insert.

