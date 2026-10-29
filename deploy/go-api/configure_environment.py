#!/usr/bin/env python3
"""Copy the authorized production DB settings without printing credential values."""
import json
import os
from pathlib import Path
import tempfile
import yaml


def configure(source, target):
    config = yaml.safe_load(Path(source).read_text())
    values = {"MONGODB_URI": config.get("MONGO_URI"), "MONGODB_DATABASE": config.get("MONGO_DBNAME"), "API_ADDR": "127.0.0.1:8091"}
    for key, value in values.items():
        if not isinstance(value, str) or not value or any(c in value for c in "\n\r\0"):
            raise ValueError(f"Missing or invalid {key}; refusing to guess production settings")
    target = Path(target)
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=target.parent, delete=False) as file:
        temporary = Path(file.name)
        try:
            os.fchmod(file.fileno(), 0o600)
            for key, value in values.items():
                file.write(f"{key}={json.dumps(value, ensure_ascii=False)}\n")
            file.flush()
            os.fsync(file.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("target")
    args = parser.parse_args()
    configure(args.source, args.target)
    print("API environment installed with mode0600; credential values were not printed")
