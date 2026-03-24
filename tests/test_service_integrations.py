import smtplib
import socket
import uuid

import boto3
import pytest
from botocore.exceptions import BotoCoreError, ClientError, EndpointConnectionError

from config import Config
from tests.conftest import (
    TEST_MAIL_HOST,
    TEST_MAIL_PORT,
    TEST_REDIS_HOST,
    TEST_REDIS_PORT,
    TEST_S3_ENDPOINT,
)


def _skip_service(name, exc):
    pytest.skip(f"{name} is not available for integration tests: {exc}")


@pytest.mark.integration
def test_redis_service_responds_to_ping():
    try:
        with socket.create_connection((TEST_REDIS_HOST, TEST_REDIS_PORT), timeout=5) as conn:
            conn.sendall(b"*1\r\n$4\r\nPING\r\n")
            response = conn.recv(64)
    except OSError as exc:
        _skip_service("Redis", exc)

    assert response.startswith(b"+PONG")


@pytest.mark.integration
def test_smtp_service_accepts_messages():
    try:
        with smtplib.SMTP(TEST_MAIL_HOST, TEST_MAIL_PORT, timeout=5) as smtp:
            code, _ = smtp.noop()
            smtp.sendmail(
                "no-reply@example.test",
                ["integration@example.test"],
                "Subject: Integration smoke\r\n\r\nSMTP smoke test",
            )
    except OSError as exc:
        _skip_service("SMTP", exc)

    assert code == 250


@pytest.mark.integration
def test_s3_service_round_trips_objects():
    client = boto3.client(
        "s3",
        endpoint_url=TEST_S3_ENDPOINT,
        aws_access_key_id=Config.ACCESS_KEY or "test",
        aws_secret_access_key=Config.S3_CONFIG.get("SECRET_KEY") or "test",
        region_name="eu-north-1",
    )

    try:
        client.list_buckets()
    except (EndpointConnectionError, BotoCoreError, OSError) as exc:
        _skip_service("LocalStack S3", exc)

    bucket_name = Config.S3_BUCKET or "mielenosoitukset-test"
    try:
        client.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={"LocationConstraint": "eu-north-1"},
        )
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
            raise

    key = f"pytest/{uuid.uuid4().hex}.txt"
    client.put_object(Bucket=bucket_name, Key=key, Body=b"service-smoke")
    result = client.get_object(Bucket=bucket_name, Key=key)

    assert result["Body"].read() == b"service-smoke"
