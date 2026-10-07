#!/usr/bin/env python3
"""Upload versioned frontend vendor files to the configured S3-backed CDN."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import boto3

from config import Config


ALLOWED_FILES = {
    "bootstrap.min.css": "text/css; charset=utf-8",
    "bootstrap.bundle.min.js": "application/javascript; charset=utf-8",
    "LICENSE": "text/plain; charset=utf-8",
}


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("asset_dir", type=Path)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    prefix = args.prefix.strip("/")
    if not prefix.startswith("vendor/") or ".." in prefix.split("/"):
        parser.error("prefix must be a versioned path below vendor/")
    if not all((args.asset_dir / name).is_file() for name in ALLOWED_FILES):
        parser.error("asset directory is missing an expected vendor file")

    client = boto3.client(
        "s3",
        aws_access_key_id=Config.ACCESS_KEY,
        aws_secret_access_key=Config.S3_SECRET_KEY,
        endpoint_url=Config.ENDPOINT_URL,
    )

    planned = []
    for filename, content_type in ALLOWED_FILES.items():
        path = args.asset_dir / filename
        key = f"{prefix}/{filename}"
        content = path.read_bytes()
        digest = sha256(content)
        exists = False
        existing_digest = None
        try:
            existing = client.head_object(Bucket=Config.S3_BUCKET, Key=key)
            exists = True
            existing_digest = (existing.get("Metadata") or {}).get("sha256")
        except client.exceptions.ClientError as exc:
            if exc.response.get("Error", {}).get("Code") not in {"404", "NoSuchKey"}:
                raise

        if exists and existing_digest != digest:
            raise RuntimeError(f"refusing to overwrite {key} with different content")
        action = "unchanged" if exists else "upload"
        print(f"{action}: {key} sha256={digest}")
        planned.append(
            {
                "action": action,
                "content": content,
                "content_type": content_type,
                "digest": digest,
                "key": key,
            }
        )

    if not args.apply:
        print("dry run only; pass --apply to upload")
        return 0

    for asset in planned:
        if asset["action"] == "upload":
            try:
                client.put_object(
                    Bucket=Config.S3_BUCKET,
                    Key=asset["key"],
                    Body=asset["content"],
                    ContentType=asset["content_type"],
                    CacheControl="public, max-age=31536000, immutable",
                    Metadata={"sha256": asset["digest"]},
                    IfNoneMatch="*",
                )
            except client.exceptions.ClientError as exc:
                if exc.response.get("Error", {}).get("Code") not in {
                    "409",
                    "412",
                    "ConditionalRequestConflict",
                    "PreconditionFailed",
                }:
                    raise
                concurrent = client.head_object(
                    Bucket=Config.S3_BUCKET,
                    Key=asset["key"],
                )
                concurrent_digest = (concurrent.get("Metadata") or {}).get("sha256")
                if concurrent_digest != asset["digest"]:
                    raise RuntimeError(
                        "concurrent publication created different content at "
                        f"{asset['key']}"
                    ) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
