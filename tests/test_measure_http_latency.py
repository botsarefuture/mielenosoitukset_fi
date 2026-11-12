import pytest

from scripts import measure_http_latency


def test_main_rejects_non_http_urls():
    with pytest.raises(SystemExit) as exc_info:
        measure_http_latency.main(["file:///etc/passwd", "--attempts", "1"])

    assert exc_info.value.code == 2


def test_summarize_reports_requested_percentiles():
    result = measure_http_latency.summarize([10, 20, 30, 40])

    assert result["count"] == 4
    assert result["p50_ms"] == 25.0
    assert result["p95_ms"] == 38.5
    assert result["p99_ms"] == 39.7
