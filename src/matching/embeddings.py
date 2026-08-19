from __future__ import annotations
import hashlib
import math
import os
import random
import re
import time
from typing import Any

DEFAULT_EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONALITY = 768
# Gemini Embedding's free tier is billed at $0; keep the rate here so every
# embedding call still gets a (attributable) cost entry without guessing a
# paid-tier price.
EMBEDDING_COST_PER_1K_INPUT = 0.0

_SIM_DIM = 4096
_SIM_FEATURES_PER_WORD = 6
_SIM_STOPWORDS = frozenset(
    """
    a an and are as at be but by for from has have he her his i in is it its
    of on or that the their them they this to was we were will with you your
    """.split()
)

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors."""
    if not a or not b:
        raise ValueError("Vectors must not be empty")
    if len(a) != len(b):
        raise ValueError(f"Vector length mismatch: {len(a)} != {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)

def _word_feature(word: str, dim: int, k: int) -> tuple[list[int], list[float]]:
    """Sparse pseudo-feature for a word: k positions with random signs,
    seeded by the word's hash so the same word always maps to the same
    feature."""
    rng = random.Random(hashlib.sha256(word.encode("utf-8")).digest())
    positions = rng.sample(range(dim), k)
    signs = [1.0 if rng.random() < 0.5 else -1.0 for _ in range(k)]
    return positions, signs

def simulate_embedding(text: str, dim: int = _SIM_DIM) -> list[float]:
    """Deterministic offline embedding: the same text always yields the same
    vector, and texts that share content words land closer together, so
    cosine ranking behaves meaningfully without any API call.
    """
    if dim < 1:
        raise ValueError("dim must be >= 1")
    words = [w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in _SIM_STOPWORDS]
    if not words:
        words = ["<empty>"]

    vec = [0.0] * dim
    for word in words:
        positions, signs = _word_feature(word, dim, _SIM_FEATURES_PER_WORD)
        for i, s in zip(positions, signs):
            vec[i] += s
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]

def embed_text(text: str, *, model: str | None = None, timeout: int = 60) -> dict[str, Any]:
    """Embed a single text string via the Gemini embeddings API.
    """
    try:
        from google import genai
    except Exception as exc:  # pragma: no cover - environment-specific
        raise RuntimeError(
            "google.genai is not installed or not importable. Install it and configure credentials."
        ) from exc

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("No Gemini API key found. Set GEMINI_API_KEY or GOOGLE_API_KEY in the environment.")

    resolved_model = model or os.environ.get("GEMINI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
    client = genai.Client(api_key=api_key)
    start = time.time()

    resp = client.models.embed_content(
        model=resolved_model,
        contents=text,
        config={
            "task_type": "SEMANTIC_SIMILARITY",
            "output_dimensionality": EMBEDDING_DIMENSIONALITY,
        },
    )
    duration_ms = int((time.time() - start) * 1000)

    try:
        vector = [float(v) for v in resp.embeddings[0].values]
    except Exception as exc:
        raise RuntimeError(f"Unexpected embedding response shape: {resp!r}") from exc

    usage = getattr(resp, "usage_metadata", None)
    input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0) if usage is not None else 0
    output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0) if usage is not None else 0
    cost_usd = round(EMBEDDING_COST_PER_1K_INPUT * input_tokens / 1000.0, 12)

    return {
        "value": vector,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "duration_ms": duration_ms,
        "model_name": resolved_model,
        "model_version": resolved_model,
        "cost_usd": cost_usd,
    }