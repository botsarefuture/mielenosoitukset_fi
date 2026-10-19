#!/usr/bin/env python3
"""Restore and verify the private media archive into local persistent S3."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import socket
import sys
import tarfile


def restore(path):
    import boto3
    from botocore.config import Config
    assert socket.gethostname() == "mielenosoitukset-pentest"
    settings = json.loads(Path("/etc/mielenosoitukset-dr/config.yaml").read_text())["S3"]
    if settings["ENDPOINT_URI"] != "http://127.0.0.1:5003":
        raise RuntimeError("Destination S3 must be local")
    client = boto3.client("s3", endpoint_url="http://127.0.0.1:5003",
                          aws_access_key_id=settings["ACCESS_KEY"], aws_secret_access_key=settings["SECRET_KEY"],
                          config=Config(max_pool_connections=8, s3={"addressing_style": "path"}))
    count = size = 0
    hashes = {}
    with tarfile.open(path, "r:") as archive:
        manifest = json.load(archive.extractfile(".dr-media-manifest.json"))
    metadata = {obj["key"]: obj for obj in manifest["objects"]}

    def upload(key, body, content_type, encoding):
        options = {"ContentType": content_type}
        if encoding:
            options["ContentEncoding"] = encoding
        result = client.put_object(Bucket="mielenosoitukset.fi", Key=key, Body=body, **options)
        assert result["ETag"].strip('"') == hashlib.md5(body).hexdigest()

    with ThreadPoolExecutor(max_workers=8) as pool, tarfile.open(path, "r|") as archive:
        pending = deque()
        for member in archive:
            if member.name == ".dr-media-manifest.json":
                manifest = json.load(archive.extractfile(member))
                continue
            assert member.isfile() and member.size <= 512 * 1024 * 1024
            body = archive.extractfile(member).read()
            hashes[member.name] = hashlib.sha256(body).hexdigest()
            item = metadata[member.name]
            assert hashes[member.name] == item["sha256"], "Object integrity failure before upload"
            encoding = member.pax_headers.get("dr.content_encoding", item.get("content_encoding", ""))
            content_type = member.pax_headers.get("dr.content_type", item["content_type"])
            # Older rehearsal archives did not record Content-Encoding. Preserve
            # gzip for encoded web assets; leave downloadable .gz files alone.
            if not encoding and body.startswith(b"\x1f\x8b") and not member.name.endswith((".gz", ".tgz", ".gzip")):
                encoding = "gzip"
            pending.append(pool.submit(upload, member.name, body, content_type, encoding))
            count += 1
            size += len(body)
            if len(pending) >= 16:
                pending.popleft().result()
        for future in pending:
            future.result()
    assert manifest is not None
    assert len(manifest["objects"]) == count
    assert all(hashes[obj["key"]] == obj["sha256"] for obj in manifest["objects"])
    actual = sum(page.get("KeyCount", len(page.get("Contents", [])))
                 for page in client.get_paginator("list_objects_v2").paginate(Bucket="mielenosoitukset.fi"))
    assert actual >= count
    print(json.dumps({"restored_objects": count, "restored_bytes": size, "hashes_verified": True,
                      "unavailable_source_objects": len(manifest.get("unavailable_objects", [])),
                      "complete_source_backup": manifest.get("complete", True)}))


if __name__ == "__main__":
    restore(Path(sys.argv[1]))
