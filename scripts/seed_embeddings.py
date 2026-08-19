"""Seed images, posts, tags, and embeddings into the database.
Run: `.venv/bin/python scripts/seed_embeddings.py`
"""
from __future__ import annotations
import csv
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from db.session import make_session_factory
from matching.embeddings import (
    DEFAULT_EMBEDDING_MODEL,
    EMBEDDING_COST_PER_1K_INPUT,
    embed_text,
    simulate_embedding,
)
from matching.repository import (
    get_images_with_metadata,
    list_posts,
    upsert_image,
    upsert_image_metadata,
    upsert_image_vector,
    upsert_post,
    upsert_post_vector,
)
from telemetry.call_logger import record_call
from vision.processor import summarize_call_metrics

def load_manifest(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))

def load_posts(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))

def load_tags(tag_dir: Path) -> dict[str, dict]:
    """Map image stem (e.g. 'redfox') -> validated tag dict."""
    tags: dict[str, dict] = {}
    for f in sorted(tag_dir.glob("*.json")):
        with f.open("r", encoding="utf-8") as fh:
            tags[f.stem] = json.load(fh)
    return tags

def build_embedder(use_real: bool):
    """Return (embed_fn, model_name). embed_fn(text) -> (vector, metrics)."""
    if use_real:
        model = os.environ.get("GEMINI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)

        def real_embed(text: str):
            rec = embed_text(text)
            return rec["value"], rec

        return real_embed, model

    def simulated_embed(text: str):
        vec = simulate_embedding(text)
        metrics = {
            "value": vec,
            "input_tokens": len(text.split()),
            "output_tokens": 0,
            "duration_ms": 0,
            "model_name": "simulated-embedding",
            "model_version": "sim-1.0",
            "cost_usd": 0.0,
        }
        return vec, metrics

    return simulated_embed, "simulated-embedding"

def seed_corpus(session) -> None:
    manifest = load_manifest(ROOT / "data" / "manifest.csv")
    tags = load_tags(ROOT / "data" / "tags")

    for row in manifest:
        filename = row["filename"]
        image_path = ROOT / "data" / "images" / filename
        image_data = image_path.read_bytes() if image_path.exists() else None
        upsert_image(
            session,
            filename=filename,
            image_data=image_data,
            author=row.get("author"),
            source_url=row.get("source_url"),
            license=row.get("license"),
        )

    from db.models import Image as ImageModel

    for stem, tag in tags.items():
        image = session.query(ImageModel).filter(ImageModel.filename == f"{stem}.jpg").one_or_none()
        if image is None:
            print(f"  WARNING: no image row for tag '{stem}.jpg', skipping")
            continue
        upsert_image_metadata(
            session,
            image_id=image.id,
            category=tag["category"],
            subject=tag["subject"],
            caption=tag["caption"],
            attributes=tag.get("attributes", []),
            confidence=tag.get("confidence", 0.0),
        )

    for row in load_posts(ROOT / "data" / "posts.csv"):
        upsert_post(session, title=row["title"], body=row["body"])

def embed_corpus(session, embed, model_name: str) -> tuple[int, int]:
    image_count = 0
    for image, meta in get_images_with_metadata(session):
        vec, metrics = embed(meta.caption)
        upsert_image_vector(session, image_id=image.id, embedding=vec, model_name=model_name)
        record_call(
            summarize_call_metrics(
                call_type="embedding",
                status="success",
                image_id=image.id,
                model_name=metrics.get("model_name"),
                model_version=metrics.get("model_version"),
                input_tokens=metrics.get("input_tokens", 0),
                output_tokens=metrics.get("output_tokens", 0),
                duration_ms=metrics.get("duration_ms", 0),
                base_cost_per_1k_input=EMBEDDING_COST_PER_1K_INPUT,
            )
        )
        image_count += 1

    post_count = 0
    for post in list_posts(session):
        vec, metrics = embed(post.body)
        upsert_post_vector(session, post_id=post.id, embedding=vec, model_name=model_name)
        record_call(
            summarize_call_metrics(
                call_type="embedding",
                status="success",
                image_id=None,
                model_name=metrics.get("model_name"),
                model_version=metrics.get("model_version"),
                input_tokens=metrics.get("input_tokens", 0),
                output_tokens=metrics.get("output_tokens", 0),
                duration_ms=metrics.get("duration_ms", 0),
                base_cost_per_1k_input=EMBEDDING_COST_PER_1K_INPUT,
            )
        )
        post_count += 1

    return image_count, post_count

def main() -> None:
    use_real = os.environ.get("USE_REAL_MODEL", "0") in ("1", "true", "True")
    embed, model_name = build_embedder(use_real)

    Session = make_session_factory()
    with Session() as session:
        seed_corpus(session)
        image_count, post_count = embed_corpus(session, embed, model_name)
        session.commit()

    print(f"Seeded embeddings into {os.environ.get('DATABASE_URL', 'data/dev.db')}")
    print(f"  image vectors: {image_count} ({'Gemini' if use_real else 'simulated'})")
    print(f"  post vectors:  {post_count}")

if __name__ == "__main__":
    main()