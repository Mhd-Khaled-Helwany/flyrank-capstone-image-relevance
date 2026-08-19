"""Run a deterministic batch tagger over images in `data/manifest.csv`.
Run: `.venv/bin/python scripts/run_batch_tagging.py`
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
import random

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from vision.schema import validate_tag_payload, TagSchema
from vision.processor import process_batch, summarize_call_metrics
from telemetry.call_logger import clear_calls, record_call
from vision.gemini_client import call_gemini_for_tag
import os

def load_manifest(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            rows.append(r)
    return rows

def normalize(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())

def pick_subject_category(filename: str) -> tuple[str, str]:
    # Try to match exactly to Subject enum values (normalized)
    from vision.schema import Subject, Category

    stem = Path(filename).stem
    n = normalize(stem)
    for s in Subject:
        if normalize(s.value) == n:
            # heuristics: map subject to category by Category membership
            # If the subject text contains a known category word, prefer that
            # Otherwise map using a small lookup based on Category keywords.
            return s.value, infer_category_from_subject(s.value)

    # fallback: infer category and subject from filename
    subj = stem.replace("-", " ").replace("_", " ")
    return subj, infer_category_from_subject(subj)

def infer_category_from_subject(subj: str) -> str:
    s = subj.lower()
    animals = {"cat", "red fox", "deer", "tiger", "owl", "wolf", "squirrel", "horse"}
    plants = {"tree", "bamboo", "cactus", "flower", "grass", "wheat"}
    vehicles = {"car", "plane", "boat", "bus", "train", "truck", "motorcycle"}
    clothing = {"pants", "t-shirt", "jacket", "hat", "gloves", "shoes", "belt"}
    furniture = {"bed", "chair", "sofa", "desk", "stool", "bookshelf", "cabinet"}
    beverage = {"coffee", "tea", "milk", "juice", "soda", "smoothie"}
    electronics = {"laptop", "phone", "camera", "headphones", "printer", "microphone", "gaming console"}

    token = s.replace("-", " ")
    for word in animals:
        if word in token:
            return "animal"
    for word in plants:
        if word in token:
            return "plant"
    for word in vehicles:
        if word in token:
            return "vehicle"
    for word in clothing:
        if word in token:
            return "clothing"
    for word in furniture:
        if word in token:
            return "furniture"
    for word in beverage:
        if word in token:
            return "beverage"
    for word in electronics:
        if word in token:
            return "electronic device"

    # fallback
    return "animal" if any(ch.isalpha() for ch in s) else "furniture"

def make_worker(manifest_rows: list[dict]):
    # worker receives filename and returns dict with 'value' and tokens
    def worker(filename: str):
        subj, cat = pick_subject_category(filename)
        payload = {
            "subject": subj,
            "category": cat,
            "attributes": [],
            "caption": f"A photo of {subj}.",
            "confidence": 0.92,
        }
        tag, errors = validate_tag_payload(payload)
        if tag is None:
            raise ValueError(f"Validation failed for {filename}: {errors}")

        persist_tag(filename, tag.model_dump())

        # simulate token usage
        input_tokens = random.randint(50, 200)
        output_tokens = random.randint(5, 40)

        return {
            "value": tag.model_dump(),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "model_name": "gemini-3.7-flash",
            "model_version": "sim-1.0",
        }

    return worker

def extract_json_object(text: str):
    if not text:
        raise ValueError("Empty model response")
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        if candidate.lower().startswith("json"):
            candidate = candidate[4:].strip()
        candidate = candidate.strip()
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = candidate[start : end + 1]
    return json.loads(candidate)

def persist_tag(filename: str, tag: dict):
    outdir = ROOT / "data" / "tags"
    outdir.mkdir(parents=True, exist_ok=True)
    outpath = outdir / (Path(filename).stem + ".json")
    with outpath.open("w", encoding="utf-8") as fh:
        json.dump(tag, fh, indent=2)


def get_tagged_image_stems() -> set[str]:
    tag_dir = ROOT / "data" / "tags"
    tag_dir.mkdir(parents=True, exist_ok=True)
    return {p.stem for p in tag_dir.glob("*.json") if p.is_file()}

def main():
    manifest = load_manifest(ROOT / "data" / "manifest.csv")
    filenames = [r["filename"] for r in manifest]
    tagged_stems = get_tagged_image_stems()
    pending = [filename for filename in filenames if Path(filename).stem not in tagged_stems]
    batch_limit = 50  # reduce the batch size if it doesn't comply with your subscription
    batch = pending[:batch_limit]

    if not batch:
        print(f"No untagged images remain. Tagged count: {len(tagged_stems)}")
        return

    clear_calls()

    # choose worker: real Gemini when USE_REAL_MODEL=1, otherwise simulated
    use_real = os.environ.get("USE_REAL_MODEL", "0") in ("1", "true", "True")

    if use_real:
        from vision.schema import Category, Subject

        valid_subjects = [s.value for s in Subject]
        valid_categories = [c.value for c in Category]
        gemini_model = os.environ.get("GEMINI_VISION_MODEL", "gemini-flash-latest")

        def real_worker(filename: str):
            # Load the actual image file (no filename in prompt to avoid bias)
            image_path = ROOT / "data" / "images" / filename
            if not image_path.exists():
                raise FileNotFoundError(f"Image not found: {image_path}")
            
            with open(image_path, "rb") as fh:
                image_bytes = fh.read()
            
            prompt = (
                "Classify this image based on ONLY what you see visually. "
                "Respond with ONLY valid JSON and no markdown fencing. "
                "The response must be parseable as JSON with keys exactly: subject, category, attributes, caption, confidence. "
                f"subject must be one of: {valid_subjects}. "
                f"category must be one of: {valid_categories}. "
                "attributes must be a JSON array of short strings (visual features). "
                "caption must be one sentence describing the image. "
                "confidence must be a float between 0.0 and 1.0. "
                "Do not include explanation or extra keys. "
                "Pick the closest valid subject/category from the allowed lists based ONLY on visual analysis."
            )
            resp = call_gemini_for_tag(prompt, model=gemini_model, image_bytes=image_bytes)

            try:
                tag_obj = extract_json_object(resp["value"])
            except Exception:
                raise ValueError(f"Failed to parse model output as JSON for {filename}: {resp.get('value')}")

            tag, errors = validate_tag_payload(tag_obj)
            if tag is None:
                raise ValueError(f"Model output failed schema validation for {filename}: {errors}")

            persist_tag(filename, tag.model_dump())

            rec = summarize_call_metrics(
                call_type="vision",
                status="success",
                image_id=None,
                model_name=resp.get("model_name"),
                model_version=resp.get("model_version"),
                input_tokens=resp.get("input_tokens", 0),
                output_tokens=resp.get("output_tokens", 0),
                duration_ms=resp.get("duration_ms", 0),
            )
            record_call(rec)
            return {
                "value": tag.model_dump(),
                "input_tokens": resp.get("input_tokens", 0),
                "output_tokens": resp.get("output_tokens", 0),
                "model_name": resp.get("model_name"),
                "model_version": resp.get("model_version"),
            }

        worker = real_worker
    else:
        worker = make_worker(manifest)

    result = process_batch(batch, worker, max_retries=2, record_calls=not use_real, call_recorder=record_call)

    print("Batch complete:")
    print(f"  processed: {len(batch)}")
    print(f"  successes: {len(result['results'])}")
    print(f"  failed: {len(result['failed'])}")
    print(f"  remaining untagged: {len([f for f in filenames if Path(f).stem not in get_tagged_image_stems()])}")

if __name__ == "__main__":
    main()
