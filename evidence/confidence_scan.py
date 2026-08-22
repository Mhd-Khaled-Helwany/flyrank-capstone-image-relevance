"""DoD §6 AI processing #2: confidence scan over tagged corpus + flagged rows.

Run: py evidence/confidence_scan.py

Prints the confidence distribution of data/tags/*.json and any DB rows where
needs_review = 1. Currently expects zero flagged images (clear-cut corpus);
after adding an ambiguous photo and re-tagging, it must list that image.
"""
import glob
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

NEEDS_REVIEW_THRESHOLD = 0.75


def main() -> None:
    confs = {
        Path(p).stem: json.load(open(p))["confidence"]
        for p in glob.glob(str(ROOT / "data" / "tags" / "*.json"))
    }
    flagged_files = [k for k, v in confs.items() if v < NEEDS_REVIEW_THRESHOLD]
    print(f"tag files: {len(confs)} | min confidence: {min(confs.values())} | "
          f"max: {max(confs.values())} | flagged (<{NEEDS_REVIEW_THRESHOLD}): {len(flagged_files)}")

    db = sqlite3.connect(ROOT / "data" / "dev.db")
    rows = db.execute(
        "SELECT i.filename, m.confidence, m.needs_review FROM image_metadata m "
        "JOIN images i ON i.id = m.image_id WHERE m.needs_review = 1"
    ).fetchall()
    print(f"image_metadata rows with needs_review=1: {len(rows)}")
    for filename, confidence, _ in rows:
        print(f"    - {filename}: confidence={confidence}")


if __name__ == "__main__":
    main()