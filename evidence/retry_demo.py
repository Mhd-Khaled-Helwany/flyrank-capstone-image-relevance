"""DoD §6 AI processing #3: batch job retries transient failures, not refusals.

Run: .venv/bin/python evidence/retry_demo.py

Simulates a flaky API (two timeouts, then success) and a policy refusal.
The timeouting item is retried with backoff until it succeeds; the refused
item is attempted exactly once and routed to `failed`.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vision.processor import process_batch


def main() -> None:
    state = {"img_flaky.jpg": 0, "img_refused.jpg": 0}

    def worker(item: str) -> str:
        state[item] += 1
        if item == "img_flaky.jpg" and state[item] <= 2:
            raise TimeoutError("read timed out")
        if item == "img_refused.jpg":
            raise RuntimeError("request refused by safety policy")
        return f"tag-ok: {item}"

    out = process_batch(
        ["img_flaky.jpg", "img_refused.jpg"], worker, max_retries=3, base_delay=0.0
    )
    print(f"succeeded: {out['results']}")
    print(f"attempts:  {state}")
    print(f"failed:    {[item for item, _ in out['failed']]}")


if __name__ == "__main__":
    main()