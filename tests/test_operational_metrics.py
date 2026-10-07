from datetime import datetime, timedelta, timezone

import pytest

from mielenosoitukset_fi.utils.operational_metrics import (
    collect_operational_metrics,
    percentile,
    summarize_samples,
)


def test_percentile_interpolates_and_rejects_invalid_range():
    assert percentile([1, 2, 3, 4], 50) == pytest.approx(2.5)
    assert percentile([1, 2, 3, 4], 95) == pytest.approx(3.85)
    assert percentile([], 99) is None
    with pytest.raises(ValueError):
        percentile([1], 101)


def test_summarize_samples_ignores_non_numeric_and_non_finite_values():
    result = summarize_samples([1, 2, None, "3", float("nan")])
    assert result == {
        "count": 2,
        "min": 1.0,
        "p50": 1.5,
        "p95": 1.95,
        "p99": 1.99,
        "max": 2.0,
    }


def test_collect_operational_metrics_uses_bounded_run_sample_and_queue_counts(db):
    db.background_job_runs.insert_many(
        [
            {"status": "success", "duration_seconds": 1.0},
            {"status": "failed", "duration_seconds": 3.0},
            {"status": "success", "duration_seconds": 100.0},
        ]
    )
    db.email_queue.insert_many(
        [
            {
                "status": "pending",
                "attempts": 0,
                "created_at": datetime.now(timezone.utc) - timedelta(minutes=2),
            },
            {"status": "in_flight", "attempts": 1},
            {"status": "failed", "attempts": 30},
        ]
    )

    result = collect_operational_metrics(db, job_sample_limit=2)

    assert result["jobs"]["sample_count"] == 2
    assert result["jobs"]["failed_count"] == 1
    assert result["jobs"]["failure_rate_pct"] == 50.0
    assert result["jobs"]["duration_seconds"]["p50"] == 51.5
    assert result["email_queue"] == {
        "total": 3,
        "pending": 1,
        "failed": 1,
        "in_flight": 1,
        "exhausted": 1,
        "oldest_age_seconds": pytest.approx(120, abs=2),
    }
