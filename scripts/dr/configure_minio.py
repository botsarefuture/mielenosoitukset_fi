#!/usr/bin/env python3
"""Give the isolated MinIO service only fresh local sandbox credentials."""
import json
import os
from pathlib import Path
import socket

if __name__ == "__main__":
    if socket.gethostname() != "mielenosoitukset-pentest" or os.getuid() != 0:
        raise RuntimeError("Run on the named sandbox only")
    config = json.loads(Path("/etc/mielenosoitukset-dr/config.yaml").read_text())["S3"]
    if config["ENDPOINT_URI"] != "http://127.0.0.1:5003":
        raise RuntimeError("S3 must point to loopback")
    for field in ["ACCESS_KEY", "SECRET_KEY"]:
        if "\n" in config[field] or "\r" in config[field]:
            raise ValueError("Invalid test credential")
    descriptor = os.open("/etc/mielenosoitukset-dr/minio.env", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write("MINIO_ROOT_USER=" + config["ACCESS_KEY"] + "\n")
        stream.write("MINIO_ROOT_PASSWORD=" + config["SECRET_KEY"] + "\n")
        stream.write("MINIO_BROWSER=off\nMINIO_UPDATE=off\n")
