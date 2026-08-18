import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from telemetry.call_logger import clear_calls, record_call, get_calls, summarize_by_image


def test_call_logger_records_and_summarizes():
    clear_calls()
    rec1 = {"image_id": 1, "cost_usd": 0.1, "total_tokens": 100, "duration_ms": 50}
    rec2 = {"image_id": 1, "cost_usd": 0.2, "total_tokens": 200, "duration_ms": 150}
    rec3 = {"image_id": 2, "cost_usd": 0.05, "total_tokens": 10, "duration_ms": 10}
    record_call(rec1)
    record_call(rec2)
    record_call(rec3)

    calls = get_calls()
    assert len(calls) == 3

    summary = summarize_by_image()
    assert summary[1]["calls"] == 2
    assert abs(summary[1]["cost_usd"] - 0.3) < 1e-9
    assert summary[2]["calls"] == 1
