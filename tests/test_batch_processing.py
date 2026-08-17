import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vision.processor import (
    compute_retry_delay,
    process_batch,
    should_retry_error,
    summarize_call_metrics,
)

def test_should_retry_only_transient_errors():
    assert should_retry_error(ConnectionError("temporary network issue")) is True
    assert should_retry_error(TimeoutError("read timed out")) is True
    assert should_retry_error(RuntimeError("HTTP 429 Too Many Requests")) is True
    assert should_retry_error(RuntimeError("503 service unavailable")) is True
    assert should_retry_error(ValueError("malformed payload")) is False
    assert should_retry_error(RuntimeError("safety policy refused the request")) is False

def test_retry_delay_uses_exponential_backoff_with_jitter():
    rng = pytest.importorskip("random").Random(7)
    delay1 = compute_retry_delay(0, base_delay=0.5, max_delay=10.0, jitter=0.75, rng=rng)
    delay2 = compute_retry_delay(1, base_delay=0.5, max_delay=10.0, jitter=0.75, rng=rng)
    assert 0.0 < delay1 < 1.0
    assert delay2 > delay1
    assert delay2 <= 10.0

def test_process_batch_retries_transient_failures_but_not_refusals():
    attempts = {"alpha": 0, "bravo": 0, "charlie": 0}

    def worker(item):
        attempts[item] += 1
        if item == "bravo" and attempts[item] == 1:
            raise TimeoutError("temporary failure")
        if item == "charlie":
            raise RuntimeError("refused by policy")
        return item.upper()

    result = process_batch(["alpha", "bravo", "charlie"], worker, max_retries=2, base_delay=0.0)

    assert result["results"] == ["ALPHA", "BRAVO"]
    assert result["failed"][0][0] == "charlie"
    assert attempts["bravo"] == 2
    assert attempts["charlie"] == 1

def test_cost_tracking_summarizes_call_metrics_and_cost():
    record = summarize_call_metrics(
        call_type="vision",
        status="success",
        image_id=7,
        model_name="gemini-flash",
        model_version="gemini-1.5-flash",
        input_tokens=120,
        output_tokens=40,
        duration_ms=1800,
        base_cost_per_1k_input=0.000075,
        base_cost_per_1k_output=0.0003,
    )

    assert record["input_tokens"] == 120
    assert record["output_tokens"] == 40
    assert record["total_tokens"] == 160
    assert record["duration_ms"] == 1800
    assert record["call_type"] == "vision"
    assert record["status"] == "success"
    assert record["image_id"] == 7
    assert record["model_name"] == "gemini-flash"
    assert record["model_version"] == "gemini-1.5-flash"
    assert record["cost_usd"] > 0
    assert record["cost_usd"] == pytest.approx((120 * 0.000075 + 40 * 0.0003) / 1000, rel=1e-9)

def test_negative_token_counts_are_rejected():
    with pytest.raises(ValueError):
        summarize_call_metrics(
            call_type="embedding",
            status="failed",
            input_tokens=-1,
            output_tokens=10,
            duration_ms=500,
        )
