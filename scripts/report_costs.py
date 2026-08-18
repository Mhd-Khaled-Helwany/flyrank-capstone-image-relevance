"""Simple reporting CLI that prints in-memory call summaries.
Run: `.venv/bin/python scripts/report_costs.py`
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from telemetry.call_logger import summarize_by_image, get_calls

def main():
    calls = get_calls()
    if not calls:
        print("No recorded calls found (in-memory logger is empty).")
        return

    summary = summarize_by_image()
    print("Per-image summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")

if __name__ == "__main__":
    main()
