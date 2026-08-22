"""DoD §6 AI processing #4: vision/embedding costs are tracked per call.

Run: .venv/bin/python evidence/cost_tracking_demo.py

Records two vision calls with the production Gemini rates and shows the
per-call log lines plus the aggregated summary. The same record shape is
produced for real API calls in gemini_client.py / seed_embeddings.py.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from telemetry.call_logger import clear_calls, get_calls, record_call, summarize_by_image
from vision.processor import summarize_call_metrics

GEMINI_INPUT_PER_1K = 0.000075
GEMINI_OUTPUT_PER_1K = 0.0003


def main() -> None:
    clear_calls()
    for image_id, inp, outp in [(1, 152, 38), (2, 131, 25)]:
        record = summarize_call_metrics(
            call_type="vision", status="success", image_id=image_id,
            model_name="gemini-flash-latest",
            input_tokens=inp, output_tokens=outp, duration_ms=900,
            base_cost_per_1k_input=GEMINI_INPUT_PER_1K,
            base_cost_per_1k_output=GEMINI_OUTPUT_PER_1K,
        )
        expected = round((inp * GEMINI_INPUT_PER_1K + outp * GEMINI_OUTPUT_PER_1K) / 1000.0, 12)
        assert record["cost_usd"] == expected
        record_call(record)

    print("--- per-call records ---")
    for call in get_calls():
        print(f"image {call['image_id']}: tokens={call['total_tokens']} cost=${call['cost_usd']:.10f}")
    print("--- aggregation ---")
    print(summarize_by_image())


if __name__ == "__main__":
    main()