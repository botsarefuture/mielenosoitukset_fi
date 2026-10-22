#!/usr/bin/env python3
"""Verify a worker build through its origin socket or public health endpoint."""

from __future__ import annotations

import argparse
import http.client
import json
import re
import socket
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


class CloudflareChallenge(RuntimeError):
    """The public probe is challenged, not an application health response."""


class UnixHTTPConnection(http.client.HTTPConnection):
    """Connect directly to Gunicorn without proxies, DNS or a CDN."""

    def __init__(self, path: str, timeout: float):
        super().__init__("localhost", timeout=timeout)
        self.path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.path)


def _report_http_failure(status: int, headers) -> None:
    # Never print response bodies, request URLs or arbitrary remote headers.
    challenge = (
        " (Cloudflare challenge)"
        if (headers or {}).get("cf-mitigated") == "challenge" else ""
    )
    print(f"Health probe returned HTTP {status}{challenge}.", file=sys.stderr)


def fetch_build_sha(
    url: str, timeout: float, *, unix_socket: str | None = None,
    detect_challenge: bool = False,
) -> str | None:
    """Read a healthy worker's build SHA, or return ``None`` on failure."""
    request = Request(
        url,
        headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
    )
    connection = None
    try:
        if unix_socket:
            target = urlsplit(url)
            if target.scheme not in ("http", "https") or not target.netloc or target.username or target.password:
                raise ValueError("Unix-socket health URL must be HTTP(S) without credentials")
            # The URL supplies only Host/path in socket mode. Accept existing
            # HTTPS overrides without making a public request or disabling TLS
            # on the separate public HTTPS verification path.
            connection = UnixHTTPConnection(unix_socket, timeout)
            path = target.path or "/"
            if target.query:
                path += "?" + target.query
            connection.request(
                "GET", path, headers={
                    "Host": target.netloc,
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                },
            )
            with connection.getresponse() as response:
                if response.status != 200:
                    _report_http_failure(response.status, response.headers)
                    return None
                payload = json.load(response)
        else:
            with urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
    except HTTPError as exc:
        _report_http_failure(exc.code, exc.headers)
        if detect_challenge and exc.code == 403 and (exc.headers or {}).get("cf-mitigated") == "challenge":
            raise CloudflareChallenge() from None
        return None
    except (
        URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError,
        OSError, http.client.HTTPException,
    ) as exc:
        print(f"Health probe failed ({type(exc).__name__}).", file=sys.stderr)
        return None
    finally:
        if connection is not None:
            connection.close()

    if not isinstance(payload, dict) or payload.get("status") != "ok":
        return None
    build_sha = payload.get("build_sha")
    return build_sha if isinstance(build_sha, str) and FULL_SHA.fullmatch(build_sha) else None


def wait_for_build(
    expected_sha: str,
    url: str,
    *,
    attempts: int,
    delay: float,
    timeout: float,
    unix_socket: str | None = None,
    detect_challenge: bool = False,
) -> bool:
    """Return true once at least one worker reports ``expected_sha``."""
    for attempt in range(1, attempts + 1):
        options = {"unix_socket": unix_socket} if unix_socket else {}
        if detect_challenge:
            options["detect_challenge"] = True
        try:
            observed_sha = fetch_build_sha(url, timeout, **options)
        except CloudflareChallenge:
            # A later challenge must not erase an earlier unhealthy/stale or
            # failed public response. Only a challenged first probe is exempt.
            if attempt > 1:
                return False
            raise
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
    parser.add_argument("--unix-socket", help="Probe Gunicorn directly over this origin socket")
    parser.add_argument(
        "--origin-verified-sha",
        help="SHA already verified over the trusted origin transport; only an explicit public Cloudflare challenge becomes a warning",
    )
    parser.add_argument("--attempts", type=int, default=30)
    parser.add_argument("--delay", type=float, default=2)
    parser.add_argument("--timeout", type=float, default=5)
    args = parser.parse_args()

    if not FULL_SHA.fullmatch(args.expected_sha):
        parser.error("expected_sha must be a full lowercase 40-character commit SHA")
    if args.attempts < 1 or args.delay < 0 or args.timeout <= 0:
        parser.error("attempts and timeout must be positive; delay cannot be negative")
    if args.unix_socket is not None:
        if not args.unix_socket:
            parser.error("--unix-socket requires a nonempty path")
        target = urlsplit(args.url)
        if target.scheme not in ("http", "https") or not target.netloc or target.username or target.password:
            parser.error("--unix-socket requires an HTTP(S) URL without credentials")
    if args.origin_verified_sha is not None:
        target = urlsplit(args.url)
        if args.origin_verified_sha != args.expected_sha:
            parser.error("--origin-verified-sha must match expected_sha")
        if args.unix_socket is not None or target.scheme != "https" or not target.netloc or target.username or target.password:
            parser.error("--origin-verified-sha requires a public HTTPS URL without credentials, not a socket probe")

    options = {"detect_challenge": True} if args.origin_verified_sha is not None else {}
    try:
        if wait_for_build(
            args.expected_sha,
            args.url,
            attempts=args.attempts,
            delay=args.delay,
            timeout=args.timeout,
            unix_socket=args.unix_socket,
            **options,
        ):
            return 0
    except CloudflareChallenge:
        print(
            "::warning::Cloudflare challenged the public health probe. "
            f"Origin already verified build {args.origin_verified_sha}; "
            "public reachability is NOT verified by this run."
        )
        return 0
    print(
        f"Health endpoint never served expected build {args.expected_sha}.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
