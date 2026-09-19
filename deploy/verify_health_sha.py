#!/usr/bin/env python3
"""Wait until the public health endpoint answers from the expected build."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def fetch_build_sha(url: str, timeout: float) -> str | None:
    """Read a healthy worker's build SHA, or return ``None`` on failure."""
    request = Request(
        url,
        headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None

    if not isinstance(payload, dict) or payload.get("status") != "ok":
        return None
    build_sha = payload.get("build_sha")
    return build_sha if isinstance(build_sha, str) else None


def wait_for_build(
    expected_sha: str,
    url: str,
    *,
    attempts: int,
    delay: float,
    timeout: float,
) -> bool:
    """Return true once at least one worker reports ``expected_sha``."""
    for attempt in range(1, attempts + 1):
        observed_sha = fetch_build_sha(url, timeout)
        if observed_sha == expected_sha:
            print(f"Health endpoint is serving expected build {expected_sha}.")
            return True
        if observed_sha:
            print(
                f"Attempt {attempt}/{attempts}: worker still serves {observed_sha}.",
                file=sys.stderr,
            )
        else:
            print(
                f"Attempt {attempt}/{attempts}: health endpoint did not return valid build metadata.",
                file=sys.stderr,
            )
        if attempt < attempts:
            time.sleep(delay)
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("expected_sha")
    parser.add_argument("url")
    parser.add_argument("--attempts", type=int, default=30)
    parser.add_argument("--delay", type=float, default=2)
    parser.add_argument("--timeout", type=float, default=5)
    args = parser.parse_args()

    if not FULL_SHA.fullmatch(args.expected_sha):
        parser.error("expected_sha must be a full lowercase 40-character commit SHA")
    if args.attempts < 1 or args.delay < 0 or args.timeout <= 0:
        parser.error("attempts and timeout must be positive; delay cannot be negative")

    if wait_for_build(
        args.expected_sha,
        args.url,
        attempts=args.attempts,
        delay=args.delay,
        timeout=args.timeout,
    ):
        return 0
    print(
        f"Health endpoint never served expected build {args.expected_sha}.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
