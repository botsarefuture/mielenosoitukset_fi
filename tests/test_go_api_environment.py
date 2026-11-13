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


@pytest.mark.parametrize("flag, expected", [(True, "true"), (None, "true"), (False, None)])
def test_event_analytics_switch_follows_the_flask_default_and_yaml_flag(tmp_path, flag, expected):
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


def test_auth_bridge_flag_is_written_from_config_and_off_by_default(tmp_path):
    path = Path(__file__).resolve().parents[1] / "deploy/go-api/configure_environment.py"
    spec = importlib.util.spec_from_file_location("go_environment", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for flag, expected in ((None, False), (False, False), (True, True)):
        source, target = tmp_path / f"c{flag}.yaml", tmp_path / f"e{flag}"
        config = {"MONGO_URI": "mongodb://127.0.0.1/isolated", "MONGO_DBNAME": "isolated"}
        if flag is not None:
            config["AUTH_BRIDGE_SCOPES"] = flag
        source.write_text(yaml.safe_dump(config))
        module.configure(source, target)
        values = dict(line.split("=", 1) for line in target.read_text().splitlines())
        assert ("AUTH_BRIDGE_ENABLED" in values) is expected
        if expected:
            assert json.loads(values["AUTH_BRIDGE_ENABLED"]) == "true"
            assert json.loads(values["AUTH_BRIDGE_SESSION_SOCKET"]).endswith("mielenosoitus.sock")
            assert json.loads(values["AUTH_BRIDGE_ORIGIN"]).startswith("https://")


def test_developer_writes_flag_needs_the_bridge_and_is_off_by_default(tmp_path):
    path = Path(__file__).resolve().parents[1] / "deploy/go-api/configure_environment.py"
    spec = importlib.util.spec_from_file_location("go_environment", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cases = (
        ({}, False),
        ({"AUTH_BRIDGE_SCOPES": True}, False),
        ({"DEVELOPER_WRITES": True}, False),  # no bridge, no writes
        ({"AUTH_BRIDGE_SCOPES": True, "DEVELOPER_WRITES": False}, False),
        ({"AUTH_BRIDGE_SCOPES": True, "DEVELOPER_WRITES": True}, True),
    )
    for index, (extra, expected) in enumerate(cases):
        source, target = tmp_path / f"c{index}.yaml", tmp_path / f"e{index}"
        source.write_text(yaml.safe_dump({"MONGO_URI": "mongodb://127.0.0.1/isolated", "MONGO_DBNAME": "isolated", **extra}))
        module.configure(source, target)
        values = dict(line.split("=", 1) for line in target.read_text().splitlines())
        assert ("DEVELOPER_WRITES_ENABLED" in values) is expected
