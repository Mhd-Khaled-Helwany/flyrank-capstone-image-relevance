"""DoD §6 AI processing #1: invalid vision responses are rejected by the schema.

Run: py evidence/invalid_tag_rejected.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vision.processor import validate_raw_response

BAD_PAYLOADS = [
    ("unknown category", {
        "subject": "red fox", "category": "electronics",
        "attributes": ["orange fur"], "caption": "A red fox", "confidence": 1.5,
    }),
    ("subject outside closed enum", {
        "subject": "dragon", "category": "animal",
        "attributes": [], "caption": "A dragon", "confidence": 0.9,
    }),
    ("missing required field", {
        "subject": "red fox", "category": "animal",
        "attributes": [], "caption": "A red fox standing in a forest",
    }),
]


def main() -> None:
    for label, payload in BAD_PAYLOADS:
        result = validate_raw_response(payload)
        verdict = "REJECTED" if not result["valid"] else "ACCEPTED"
        print(f"[{verdict}] {label}: {len(result.get('errors', []))} schema error(s)")
        for err in result.get("errors", []):
            field = err["loc"][0] if err["loc"] else "<model>"
            print(f"    - {field}: {err['msg']}")


if __name__ == "__main__":
    main()