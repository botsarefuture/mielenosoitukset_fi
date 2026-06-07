from bson import ObjectId


class _FakeSuggestionsCollection:
    def __init__(self):
        self.docs = []

    def find_one(self, query):
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                return dict(doc)
        return None

    def update_one(self, query, update, upsert=False):
        doc = self.find_one(query)
        if doc is None:
            doc = dict(query)
            doc.update(update.get("$setOnInsert", {}))
            self.docs.append(doc)
        doc.update(update.get("$set", {}))
        for index, existing in enumerate(self.docs):
            if all(existing.get(key) == query.get(key) for key in query):
                self.docs[index] = doc
                break

    def create_index(self, *args, **kwargs):
        return None


def test_get_or_create_deepl_suggestions_for_demo_caches_result(monkeypatch):
    from mielenosoitukset_fi.utils import demo_translation_cache as cache_module

    fake_collection = _FakeSuggestionsCollection()
    monkeypatch.setattr(
        cache_module,
        "translation_suggestions_collection",
        fake_collection,
    )

    calls = []

    def fake_builder(source_payload, source_language, target_languages, **kwargs):
        calls.append((source_payload, source_language, list(target_languages)))
        return {
            "en": {
                "title": "English title",
                "description": "English description",
                "tags": ["peace"],
                "_meta": {
                    "provider": "deepl",
                    "source_language": source_language,
                    "target_language": "en",
                    "auto_generated": True,
                },
            }
        }

    monkeypatch.setattr(
        cache_module,
        "build_deepl_translation_suggestions",
        fake_builder,
    )

    demo = {
        "_id": ObjectId(),
        "title": "Suomenkielinen otsikko",
        "description": "Suomenkielinen kuvaus",
        "tags": ["rauha"],
        "default_language": "fi",
    }

    first = cache_module.get_or_create_deepl_suggestions_for_demo(demo, ["en"])
    second = cache_module.get_or_create_deepl_suggestions_for_demo(demo, ["en"])

    assert first["cached"] is False
    assert second["cached"] is True
    assert first["suggestions"]["en"]["title"] == "English title"
    assert second["suggestions"]["en"]["title"] == "English title"
    assert len(calls) == 1


def test_get_or_create_deepl_suggestions_for_demo_refreshes_when_source_changes(monkeypatch):
    from mielenosoitukset_fi.utils import demo_translation_cache as cache_module

    fake_collection = _FakeSuggestionsCollection()
    monkeypatch.setattr(
        cache_module,
        "translation_suggestions_collection",
        fake_collection,
    )

    counter = {"count": 0}

    def fake_builder(source_payload, source_language, target_languages, **kwargs):
        counter["count"] += 1
        return {
            "en": {
                "title": f"English title {counter['count']}",
                "description": "English description",
                "tags": ["peace"],
                "_meta": {
                    "provider": "deepl",
                    "source_language": source_language,
                    "target_language": "en",
                    "auto_generated": True,
                },
            }
        }

    monkeypatch.setattr(
        cache_module,
        "build_deepl_translation_suggestions",
        fake_builder,
    )

    demo = {
        "_id": ObjectId(),
        "title": "Suomenkielinen otsikko",
        "description": "Suomenkielinen kuvaus",
        "tags": ["rauha"],
        "default_language": "fi",
    }

    first = cache_module.get_or_create_deepl_suggestions_for_demo(demo, ["en"])
    demo["description"] = "Muuttunut kuvaus"
    second = cache_module.get_or_create_deepl_suggestions_for_demo(demo, ["en"])

    assert first["source_hash"] != second["source_hash"]
    assert second["cached"] is False
    assert second["suggestions"]["en"]["title"] == "English title 2"


def test_get_or_create_deepl_suggestions_for_demo_skips_past_demos_by_default(monkeypatch):
    from mielenosoitukset_fi.utils import demo_translation_cache as cache_module

    fake_collection = _FakeSuggestionsCollection()
    monkeypatch.setattr(
        cache_module,
        "translation_suggestions_collection",
        fake_collection,
    )

    calls = []

    def fake_builder(source_payload, source_language, target_languages, **kwargs):
        calls.append(True)
        return {}

    monkeypatch.setattr(
        cache_module,
        "build_deepl_translation_suggestions",
        fake_builder,
    )

    result = cache_module.get_or_create_deepl_suggestions_for_demo(
        {
            "_id": ObjectId(),
            "title": "Vanha demo",
            "description": "Kuvaus",
            "tags": ["rauha"],
            "default_language": "fi",
            "date": "2020-01-01",
        },
        ["en"],
    )

    assert result["skipped"] is True
    assert result["reason"] == "past_demo"
    assert result["suggestions"] == {}
    assert calls == []
