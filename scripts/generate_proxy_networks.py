"""Generate Go's trusted proxy data from Flask's existing security policy."""
import argparse
import ast
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root / "mielenosoitukset_fi/utils/request_ip.py").read_text())
    networks = next(ast.literal_eval(node.value) for node in tree.body if
                    isinstance(node, ast.Assign) and any(isinstance(name, ast.Name) and
                    name.id == "CLOUDFLARE_NETWORKS" for name in node.targets))
    content = json.dumps(networks, indent=2) + "\n"
    target = root / "go-api/cloudflare_networks.json"
    if args.check:
        if target.read_text() != content:
            raise SystemExit("Trusted proxy data is stale; regenerate it")
    else:
        target.write_text(content)


if __name__ == "__main__":
    main()
