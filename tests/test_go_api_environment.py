"""The opt-in Go writer must accept the same content languages as Flask."""
import importlib.util
import json
from pathlib import Path

import pytest
import yaml


@pytest.mark.parametrize("babel, expected", [
    ({}, ["fi", "en"]),
    ({"SUPPORTED_LOCALES": ["fi", "en", "sv"]}, ["fi", "en", "sv"]),
    ({"SUPPORTED_LOCALES": ["fi", "sv"]}, ["fi", "sv"]),
    ({"SUPPORTED_LOCALES": []}, ["fi"]),
])
def test_submission_locales_follow_nested_flask_configuration(tmp_path, babel, expected):
    path = Path(__file__).resolve().parents[1] / "deploy/go-api/configure_environment.py"
    spec = importlib.util.spec_from_file_location("go_environment", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source, target = tmp_path / "config.yaml", tmp_path / "environment"
    source.write_text(yaml.safe_dump({
        "MONGO_URI": "mongodb://127.0.0.1/isolated", "MONGO_DBNAME": "isolated",
        "SECRET_KEY": "test-secret-not-for-production-" * 2, "GO_SUBMIT_ENABLED": True, "BABEL": babel,
    }))
    module.configure(source, target)
    values = dict(line.split("=", 1) for line in target.read_text().splitlines())
    assert json.loads(values["PUBLIC_SUBMIT_LOCALES"]).split(",") == expected


@pytest.mark.parametrize("flag, expected", [(True, "true"), (False, None), (None, None), ("true", None)])
def test_event_analytics_switch_follows_the_flask_yaml_flag(tmp_path, flag, expected):
    path = Path(__file__).resolve().parents[1] / "deploy/go-api/configure_environment.py"
    spec = importlib.util.spec_from_file_location("go_environment", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source, target = tmp_path / "config.yaml", tmp_path / "environment"
    config = {"MONGO_URI": "mongodb://127.0.0.1/isolated", "MONGO_DBNAME": "isolated"}
    if flag is not None:
        config["SITE_ANALYTICS_ENABLED"] = flag
    source.write_text(yaml.safe_dump(config))
    module.configure(source, target)
    values = dict(line.split("=", 1) for line in target.read_text().splitlines())
    assert (json.loads(values["SITE_ANALYTICS_ENABLED"]) if "SITE_ANALYTICS_ENABLED" in values else None) == expected
