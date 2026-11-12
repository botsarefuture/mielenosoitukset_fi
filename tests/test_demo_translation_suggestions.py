from unittest.mock import Mock

import pytest

from config import Config
from mielenosoitukset_fi.utils.demo_translation_suggestions import (
    build_deepl_translation_suggestions,
)


def test_build_deepl_translation_suggestions_returns_structured_proposals(monkeypatch):
    monkeypatch.setattr(Config, "DEEPL_API_KEY", "test-deepl-key")
    monkeypatch.setattr(
        Config,
        "DEEPL_API_URL",
        "https://api-free.deepl.com/v2/translate",
    )

    fake_response = Mock()
    fake_response.json.return_value = {
        "translations": [
            {"text": "English title"},
            {"text": "English description"},
            {"text": "peace, climate"},
        ]
    }
    fake_response.raise_for_status.return_value = None

    post_mock = Mock(return_value=fake_response)
    monkeypatch.setattr(
        "mielenosoitukset_fi.utils.demo_translation_suggestions.requests.post",
        post_mock,
    )

    suggestions = build_deepl_translation_suggestions(
        {
            "title": "Suomenkielinen otsikko",
            "description": "Suomenkielinen kuvaus",
            "tags": ["rauha", "ilmasto"],
        },
        source_language="fi",
        target_languages=["en"],
    )

    assert suggestions["en"]["title"] == "English title"
    assert suggestions["en"]["description"] == "English description"
    assert suggestions["en"]["tags"] == ["peace", "climate"]
    assert suggestions["en"]["_meta"]["provider"] == "deepl"
    assert suggestions["en"]["_meta"]["source_language"] == "fi"
    assert suggestions["en"]["_meta"]["target_language"] == "en"

    post_mock.assert_called_once()
    payload = post_mock.call_args.kwargs["data"]
    assert payload["source_lang"] == "FI"
    assert payload["target_lang"] == "EN"
    assert payload["text"] == [
        "Suomenkielinen otsikko",
        "Suomenkielinen kuvaus",
        "rauha, ilmasto",
    ]


def test_build_deepl_translation_suggestions_requires_configuration(monkeypatch):
    monkeypatch.setattr(Config, "DEEPL_API_KEY", "")

    with pytest.raises(RuntimeError, match="DeepL API key is not configured"):
        build_deepl_translation_suggestions(
            {"title": "Otsikko", "description": "Kuvaus", "tags": ["rauha"]},
            source_language="fi",
            target_languages=["en"],
        )
