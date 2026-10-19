#!/usr/bin/env python3
"""Create only the sandbox bucket and local read policy behind nginx auth."""
import json
from pathlib import Path
import socket

if __name__ == "__main__":
    import boto3
    if socket.gethostname() != "mielenosoitukset-pentest":
        raise RuntimeError("Run on the sandbox only")
    settings = json.loads(Path("/etc/mielenosoitukset-dr/config.yaml").read_text())["S3"]
    if settings["ENDPOINT_URI"] != "http://127.0.0.1:5003":
        raise RuntimeError("S3 must be local")
    client = boto3.client("s3", endpoint_url=settings["ENDPOINT_URI"],
                          aws_access_key_id=settings["ACCESS_KEY"], aws_secret_access_key=settings["SECRET_KEY"])
    bucket = settings["BUCKET"]
    if bucket != "mielenosoitukset.fi":
        raise RuntimeError("Unexpected bucket")
    if bucket not in [item["Name"] for item in client.list_buckets()["Buckets"]]:
        client.create_bucket(Bucket=bucket)
    client.put_bucket_policy(Bucket=bucket, Policy=json.dumps({
        "Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"AWS": ["*"]},
        "Action": ["s3:GetObject"], "Resource": ["arn:aws:s3:::" + bucket + "/*"]}],
    }))
    print("Local bucket ready; MinIO listens only on loopback and nginx media access requires authentication")
