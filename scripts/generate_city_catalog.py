#!/usr/bin/env python3
"""Generate shared Go/React city data from existing structured project sources."""
import ast
import argparse
import json
from pathlib import Path
import unicodedata

ROOT = Path(__file__).resolve().parents[1]


def constant(path, name):
    for node in ast.parse((ROOT / path).read_text()).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise ValueError(f"Missing city source constant: {name}")


def city_key(name):
    value = unicodedata.normalize("NFKD", name.strip().casefold())
    value = value.encode("ascii", "ignore").decode("ascii")
    return "-".join(value.replace("_", "-").split())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    names = json.loads((ROOT / "mielenosoitukset_fi/utils/data/city_list.json").read_text())
    phrases = constant("mielenosoitukset_fi/basic_routes.py", "CITY_INESSIVE_OVERRIDES")
    defaults = constant("mielenosoitukset_fi/utils/city_settings.py", "DEFAULT_ACTIVE_CITY_NAMES")
    rows = [{"key": city_key(name), "name": name,
             "phrase": phrases.get(city_key(name), f"kaupungissa {name}"),
             "default_enabled": name in defaults} for name in names]
    output = json.dumps(rows, ensure_ascii=False, indent=2) + "\n"
    target = ROOT / "go-api/city_catalog.json"
    if args.check:
        if target.read_text() != output:
            raise SystemExit("City catalog is stale: run python3 scripts/generate_city_catalog.py")
    else:
        target.write_text(output)


if __name__ == "__main__":
    main()
