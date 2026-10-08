"""Read-only operational metrics for status views and diagnostics."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from numbers import Real
from typing import Iterable


def percentile(values: Iterable[Real], percentile_value: float) -> float | None:
    """Return a linearly interpolated percentile for finite numeric values."""
    if not 0 <= percentile_value <= 100:
        raise ValueError("percentile_value must be between 0 and 100")

    samples = sorted(
        float(value)
        for value in values
        if isinstance(value, Real) and math.isfinite(float(value))
    )
    if not samples:
        return None
    if len(samples) == 1:
        return samples[0]

    rank = (len(samples) - 1) * percentile_value / 100
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return samples[lower]

    weight = rank - lower
    return samples[lower] + (samples[upper] - samples[lower]) * weight


def summarize_samples(values: Iterable[Real], *, digits: int = 3) -> dict:
    """Summarize numeric samples with p50, p95 and p99 percentiles."""
    samples = [
        float(value)
        for value in values
        if isinstance(value, Real) and math.isfinite(float(value))
    ]
    if not samples:
        return {
            "count": 0,
            "min": None,
            "p50": None,
            "p95": None,
            "p99": None,
            "max": None,
        }

    def rounded(value: float | None) -> float | None:
        return round(value, digits) if value is not None else None

    return {
        "count": len(samples),
        "min": rounded(min(samples)),
        "p50": rounded(percentile(samples, 50)),
        "p95": rounded(percentile(samples, 95)),
        "p99": rounded(percentile(samples, 99)),
        "max": rounded(max(samples)),
    }


def _age_seconds(value: object, now: datetime) -> int | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return max(0, round((now - value.astimezone(timezone.utc)).total_seconds()))


def collect_operational_metrics(db, *, job_sample_limit: int = 500) -> dict:
    """Collect bounded, read-only background-job and email-queue metrics."""
    job_sample_limit = max(1, min(int(job_sample_limit), 5000))
    job_runs = list(
        db["background_job_runs"]
        .find(
            {},
            {
                "duration_seconds": 1,
                "status": 1,
                "finished_at": 1,
                "started_at": 1,
            },
        )
        .sort("_id", -1)
        .limit(job_sample_limit)
    )
    durations = [run.get("duration_seconds") for run in job_runs]
    job_duration = summarize_samples(durations)
    failed_runs = sum(
        1 for run in job_runs if run.get("status") in {"error", "failed"}
    )

    queue = db["email_queue"]
    pending_query = {"status": {"$in": [None, "pending"]}}
    failed_query = {"status": "failed"}
    in_flight_query = {"status": "in_flight"}
    exhausted_query = {"status": "failed", "attempts": {"$gte": 30}}

    eligible_status = {"status": {"$in": [None, "pending", "failed", "in_flight"]}}
    oldest_created = queue.find_one(
        {**eligible_status, "created_at": {"$type": "date"}},
        {"created_at": 1},
        sort=[("created_at", 1)],
    )
    oldest_queued = queue.find_one(
        {
            **eligible_status,
            "created_at": {"$not": {"$type": "date"}},
            "queued_at": {"$type": "date"},
        },
        {"queued_at": 1},
        sort=[("queued_at", 1)],
    )
    timestamp_candidates = [
        timestamp
        for timestamp in (
            oldest_created.get("created_at") if oldest_created else None,
            oldest_queued.get("queued_at") if oldest_queued else None,
        )
        if isinstance(timestamp, datetime)
    ]
    oldest_timestamp = min(timestamp_candidates) if timestamp_candidates else None

    now = datetime.now(timezone.utc)
    return {
        "jobs": {
            "sample_count": len(job_runs),
            "failed_count": failed_runs,
            "failure_rate_pct": (
                round(failed_runs / len(job_runs) * 100, 1) if job_runs else None
            ),
            "duration_seconds": job_duration,
        },
        "email_queue": {
            "total": queue.count_documents({}),
            "pending": queue.count_documents(pending_query),
            "failed": queue.count_documents(failed_query),
            "in_flight": queue.count_documents(in_flight_query),
            "exhausted": queue.count_documents(exhausted_query),
            "oldest_age_seconds": _age_seconds(oldest_timestamp, now),
        },
    }
