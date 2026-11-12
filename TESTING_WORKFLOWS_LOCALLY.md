# Testing GitHub Actions Workflows Locally

This guide explains how to run and test GitHub Actions workflows on your local machine before pushing to GitHub.

## Option 1: Using `act` (Recommended)

[`act`](https://github.com/nektos/act) is a tool that runs GitHub Actions locally using Docker.

### Installation

**On macOS (via Homebrew):**
```bash
brew install act
```

**On Ubuntu/Debian (via apt):**
```bash
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
```

**On Linux (direct download):**
```bash
curl -s https://raw.githubusercontent.com/nektos/act/master/install.sh | bash
```

### Running the Tests Workflow Locally

```bash
# Run the full tests workflow
act -j python-tests

# Run with more verbose output
act -j python-tests -v

# Run a specific event (push, pull_request, etc.)
act push -j python-tests

# Run with custom environment variables
act -j python-tests -e- <<< '{"some_var": "value"}'
```

### Common Issues With `act`

**Issue:** `act` uses the `linux/amd64` runner image by default, but you might be on `arm64` (Apple Silicon, etc.)

**Solution:**
```bash
act -j python-tests --container-architecture linux/amd64
```

**Issue:** Services not starting properly in `act`

**Solution:** `act` doesn't handle `docker compose` perfectly. Use Option 2 instead.

---

## Option 2: Manual Testing (Most Reliable)

Run the workflow steps manually on your machine:

```bash
# 1. Set up Python
python -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements-dev.txt

# 3. Install Playwright
python -m playwright install --with-deps chromium

# 4. Start services
docker compose -f compose.test.yml up -d mongo redis localstack mailpit

# 5. Wait for services (built into compose.test.yml now)
docker compose -f compose.test.yml ps

# Check health status:
docker compose -f compose.test.yml ps --format "table {{.Service}}\t{{.Status}}"

# 6. Initialize LocalStack bucket (from workflow)
python - <<'PY'
import boto3
from botocore.exceptions import ClientError

client = boto3.client(
    "s3",
    endpoint_url="http://127.0.0.1:4566",
    aws_access_key_id="test",
    aws_secret_access_key="test",
    region_name="eu-north-1",
)
try:
    client.create_bucket(Bucket="mielenosoitukset-test")
except ClientError as exc:
    error_code = exc.response.get("Error", {}).get("Code")
    if error_code not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
        raise
PY

# 7. Run tests
pytest

# 8. Tear down when done
docker compose -f compose.test.yml down -v
```

---

## Option 3: Create a Local Test Script

Create a `test-locally.sh` script in your repo root:

```bash
#!/bin/bash
set -e

echo "🚀 Starting local GitHub Actions test..."

# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
python -m playwright install --with-deps chromium

# Start services
echo "📦 Starting Docker services..."
docker compose -f compose.test.yml up -d mongo redis localstack mailpit

# Health check
echo "⏳ Waiting for services..."
python - <<'PY'
import socket, time, urllib.request
checks = [
    ("mongo", "socket", ("127.0.0.1", 27017)),
    ("redis", "socket", ("127.0.0.1", 6379)),
    ("localstack", "http", "http://127.0.0.1:4566/_localstack/health"),
    ("mailpit", "http", "http://127.0.0.1:8025/api/v1/info"),
]
deadline = time.time() + 240
pending = list(checks)
while pending and time.time() < deadline:
    remaining = []
    for name, check_type, target in pending:
        try:
            if check_type == "socket":
                with socket.create_connection(target, timeout=2):
                    pass
            else:
                with urllib.request.urlopen(target, timeout=2) as response:
                    if response.status >= 400:
                        raise RuntimeError(f"{name} returned {response.status}")
        except Exception:
            remaining.append((name, check_type, target))
    if not remaining:
        break
    time.sleep(2)
    pending = remaining
if pending:
    names = ", ".join(name for name, _, _ in pending)
    raise SystemExit(f"Timed out waiting for: {names}")
PY

# Initialize bucket
echo "🪣 Initializing S3 bucket..."
python - <<'PY'
import boto3
from botocore.exceptions import ClientError

client = boto3.client(
    "s3",
    endpoint_url="http://127.0.0.1:4566",
    aws_access_key_id="test",
    aws_secret_access_key="test",
    region_name="eu-north-1",
)
try:
    client.create_bucket(Bucket="mielenosoitukset-test")
except ClientError as exc:
    error_code = exc.response.get("Error", {}).get("Code")
    if error_code not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
        raise
PY

# Run tests
echo "🧪 Running tests..."
pytest

# Cleanup
echo "🧹 Cleaning up..."
docker compose -f compose.test.yml down -v

echo "✅ All tests passed!"
```

Then run it:
```bash
chmod +x test-locally.sh
./test-locally.sh
```

---

## Debugging Failed Services

If services don't start properly:

```bash
# Check service status
docker compose -f compose.test.yml ps

# View logs for a specific service
docker compose -f compose.test.yml logs localstack
docker compose -f compose.test.yml logs mongo
docker compose -f compose.test.yml logs redis
docker compose -f compose.test.yml logs mailpit

# View all logs in real-time
docker compose -f compose.test.yml logs -f

# Check if ports are in use
lsof -i :27017  # MongoDB
lsof -i :6379   # Redis
lsof -i :4566   # LocalStack
lsof -i :1025   # Mailpit
lsof -i :8025   # Mailpit Web UI
```

---

## Summary of Changes Made

✅ **compose.test.yml**
- Added healthcheck for LocalStack with 10s start period

✅ **.github/workflows/tests.yml**
- Increased job timeout from 20 to 30 minutes
- Increased health check timeout from 120 to 240 seconds
- Added progress output during health checks
- Added `docker compose ps` debug output
- Added service logs dump if health check fails
- Better labeled teardown and failure logging

These changes make the workflow more reliable on slower CI runners.
