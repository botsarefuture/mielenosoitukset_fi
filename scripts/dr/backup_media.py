#!/usr/bin/env python3
"""Stream the site's S3 bucket to a private tar archive, using read-only calls."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import sys
import tarfile
import time


def backup(config_path, endpoint_override=None):
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError
    import yaml
    config = yaml.safe_load(Path(config_path).read_text())["S3"]
    if endpoint_override:
        from urllib.parse import urlsplit
        endpoint = urlsplit(endpoint_override)
        if endpoint.scheme != "http" or endpoint.hostname != "127.0.0.1" or endpoint.port != 9000:
            raise ValueError("Only the verified local source S3 endpoint is permitted")
    client = boto3.client("s3", aws_access_key_id=config["ACCESS_KEY"],
                          aws_secret_access_key=config["SECRET_KEY"],
                          endpoint_url=endpoint_override or config["ENDPOINT_URI"],
                          config=Config(max_pool_connections=8))
    bucket = config.get("BUCKET", "mielenosoitukset.fi")
    assert bucket == "mielenosoitukset.fi"
    objects = (obj for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket)
               for obj in page.get("Contents", []))

    def fetch(obj):
        key = obj["Key"]
        if key.startswith("/") or ".." in PurePosixPath(key).parts:
            raise ValueError("Unsafe object key")
        for attempt in range(2):
            try:
                response = client.get_object(Bucket=bucket, Key=key, IfMatch=obj["ETag"])
                break
            except ClientError as error:
                status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                if status not in {403, 404, 412}:
                    raise
                if status == 403 and attempt == 0:
                    time.sleep(1)
                    continue
                return key, None, str(status), ""
        data = response["Body"].read()
        assert len(data) == obj["Size"]
        return key, data, response.get("ContentType", "application/octet-stream"), response.get("ContentEncoding", "")

    manifest = []
    unavailable = []
    with ThreadPoolExecutor(max_workers=8) as pool, tarfile.open(fileobj=sys.stdout.buffer, mode="w|") as archive:
        pending = deque()
        for _ in range(8):
            obj = next(objects, None)
            if obj is not None:
                pending.append(pool.submit(fetch, obj))
        while pending:
            key, data, content_type, content_encoding = pending.popleft().result()
            if data is None:
                unavailable.append({"key": key, "status": content_type})
            else:
                info = tarfile.TarInfo(key)
                info.size = len(data)
                info.mode = 0o640
                info.pax_headers = {"dr.content_type": content_type, "dr.content_encoding": content_encoding}
                archive.addfile(info, io.BytesIO(data))
                manifest.append({"key": key, "bytes": len(data), "content_type": content_type, "content_encoding": content_encoding,
                                 "sha256": hashlib.sha256(data).hexdigest()})
            obj = next(objects, None)
            if obj is not None:
                pending.append(pool.submit(fetch, obj))
        payload = json.dumps({"objects": manifest, "unavailable_objects": unavailable,
                              "complete": not unavailable}, separators=(",", ":")).encode()
        info = tarfile.TarInfo(".dr-media-manifest.json")
        info.size = len(payload)
        info.mode = 0o600
        archive.addfile(info, io.BytesIO(payload))
    return 2 if unavailable else 0


if __name__ == "__main__":
    if len(sys.argv) not in {2, 3}:
        raise SystemExit("Usage: backup_media.py /private/app/config.yaml [http://127.0.0.1:9000]")
    raise SystemExit(backup(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else None))
