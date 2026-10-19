#!/usr/bin/env python3
"""Stream a logical backup to stdout without exposing its source credentials.

Linux source host needs mongodump and PyYAML. Reads the application YAML locally;
the credential-bearing tool configuration exists only in an anonymous memfd.
This does not coordinate live writers or provide a cross-collection PIT snapshot.
"""
import argparse
import json
import os
import re
from pathlib import Path
import subprocess
import sys
from urllib.parse import parse_qs, unquote, urlsplit


def authentication_database(uri):
    parsed = urlsplit(uri)
    return parse_qs(parsed.query).get("authSource", [unquote(parsed.path.strip("/")) or "admin"])[0]


def backup(config_path):
    import yaml
    config = yaml.safe_load(Path(config_path).read_text())
    if config.get("MONGO_DBNAME") != "mielenosoitukset":
        raise ValueError("Unexpected database name; refusing backup")
    uri = config["MONGO_URI"]
    if not uri.startswith(("mongodb://", "mongodb+srv://")):
        raise ValueError("Invalid MongoDB configuration")
    descriptor = os.memfd_create("dr-mongodump-config", 0)
    try:
        os.write(descriptor, json.dumps({"uri": uri}).encode())
        os.lseek(descriptor, 0, os.SEEK_SET)
        result = subprocess.run([
            "nice", "-n", "10", "mongodump", f"--config=/proc/self/fd/{descriptor}",
            "--db=mielenosoitukset", "--authenticationDatabase=" + authentication_database(uri),
            "--numParallelCollections=1", "--archive", "--gzip",
        ], pass_fds=(descriptor,), stdout=sys.stdout.buffer, stderr=subprocess.PIPE)
        if result.returncode:
            # Never echo credential-bearing tool diagnostics.
            error = result.stderr.decode(errors="replace").replace(uri, "[redacted]")
            error = re.sub(r"mongodb(?:\+srv)?://[^\s]+", "[redacted]", error)
            parsed = urlsplit(uri)
            for secret in [parsed.username, parsed.password]:
                if secret:
                    error = error.replace(secret, "[redacted]").replace(unquote(secret), "[redacted]")
            raise RuntimeError("mongodump failed: " + error[:1000])
    finally:
        os.close(descriptor)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config_path", type=Path)
    backup(parser.parse_args().config_path)
