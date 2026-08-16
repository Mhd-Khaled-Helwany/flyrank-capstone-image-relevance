import json
from __future__ import annotations
from typing import Any
from .schema import validate_tag_payload, TagSchema

def validate_raw_response(raw: dict) -> dict:
    tag, errors = validate_tag_payload(raw)
    if tag is not None:
        return {"valid": True, "tag": tag.model_dump()} 
    else:
        return {"valid": False, "errors": errors, "raw_response": raw}

def validate_from_json_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return validate_raw_response(raw)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate a sample vision model JSON")
    parser.add_argument("json_file", help="Path to JSON file to validate")
    args = parser.parse_args()
    result = validate_from_json_file(args.json_file)
    print(json.dumps(result, indent=2))
