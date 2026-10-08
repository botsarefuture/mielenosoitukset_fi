#!/usr/bin/env python3
"""Measure HTTP response latency with a small sequential sample."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import time
import urllib.parse


MAX_RESPONSE_BYTES = 5 * 1024 * 1024


def percentile(values, percentile_value):
    samples = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not samples:
        return None
    if len(samples) == 1:
        return samples[0]
    rank = (len(samples) - 1) * percentile_value / 100
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return samples[lower]
    return samples[lower] + (samples[upper] - samples[lower]) * (rank - lower)


def summarize(samples):
    def rounded(value):
        return round(value, 1) if value is not None else None

    return {
        "count": len(samples),
        "min_ms": rounded(min(samples)) if samples else None,
        "p50_ms": rounded(percentile(samples, 50)),
        "p95_ms": rounded(percentile(samples, 95)),
        "p99_ms": rounded(percentile(samples, 99)),
        "max_ms": rounded(max(samples)) if samples else None,
    }


def measure(url, *, attempts, warmup, timeout, delay):
    samples = []
    failures = []
    for index in range(warmup + attempts):
        try:
            completed = subprocess.run(
                [
                    "curl",
                    "--disable",
                    "--silent",
                    "--show-error",
                    "--location",
                    "--max-redirs",
                    "5",
                    "--proto",
                    "=http,https",
                    "--proto-redir",
                    "=http,https",
                    "--max-time",
                    str(timeout),
                    "--max-filesize",
                    str(MAX_RESPONSE_BYTES),
                    "--user-agent",
                    "mielenosoitukset-fi-latency-probe/1.0",
                    "--output",
                    "/dev/null",
                    "--write-out",
                    "%{http_code}\t%{time_total}",
                    "--",
                    url,
                ],
                capture_output=True,
                text=True,
                timeout=timeout + 1,
                check=False,
            )
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr.strip() or "curl request failed")
            status_text, elapsed_text = completed.stdout.rsplit("\t", 1)
            status = int(status_text)
            elapsed_ms = float(elapsed_text) * 1000
            if index >= warmup:
                if 200 <= status < 400:
                    samples.append(elapsed_ms)
                else:
                    failures.append({"status": status})
        except (RuntimeError, subprocess.TimeoutExpired, ValueError) as exc:
            if index >= warmup:
                failures.append({"error": str(exc)})
        if delay and index < warmup + attempts - 1:
            time.sleep(delay)

    return {
        "url": url,
        "attempts": attempts,
        "successes": len(samples),
        "failures": len(failures),
        **summarize(samples),
        "failure_details": failures[:5],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urls", nargs="+", help="HTTP(S) URLs to measure")
    parser.add_argument("--attempts", type=int, default=30)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--delay", type=float, default=0.1)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    if args.attempts < 1 or args.warmup < 0 or args.timeout <= 0 or args.delay < 0:
        parser.error("attempts/timeout must be positive; warmup/delay cannot be negative")
    if shutil.which("curl") is None:
        parser.error("curl is required for bounded HTTP measurements")
    for url in args.urls:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme.lower() not in {"http", "https"}:
            parser.error(f"only HTTP(S) URLs are supported: {url}")
        if parsed.username is not None or parsed.password is not None:
            parser.error("URLs containing credentials are not supported")

    results = [
        measure(
            url,
            attempts=args.attempts,
            warmup=args.warmup,
            timeout=args.timeout,
            delay=args.delay,
        )
        for url in args.urls
    ]
    if args.as_json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for result in results:
            print(
                f"{result['url']}: {result['successes']}/{result['attempts']} OK, "
                f"p50 {result['p50_ms']} ms, p95 {result['p95_ms']} ms, "
                f"p99 {result['p99_ms']} ms, max {result['max_ms']} ms"
            )
    return 1 if any(result["failures"] for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
