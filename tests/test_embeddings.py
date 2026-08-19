import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from matching.embeddings import cosine_similarity, embed_text, simulate_embedding


def test_cosine_identical_vectors_is_1():
    assert cosine_similarity([1.0, 0.0, 0.0], [1.0, 0.0, 0.0]) == pytest.approx(1.0)


def test_cosine_orthogonal_vectors_is_0():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_known_value():
    assert cosine_similarity([1.0, 1.0], [1.0, 0.0]) == pytest.approx(1.0 / math.sqrt(2))


def test_cosine_zero_vector_is_0():
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == pytest.approx(0.0)


def test_cosine_rejects_empty_vectors():
    with pytest.raises(ValueError):
        cosine_similarity([], [1.0])
    with pytest.raises(ValueError):
        cosine_similarity([1.0], [])


def test_cosine_rejects_length_mismatch():
    with pytest.raises(ValueError):
        cosine_similarity([1.0, 2.0], [1.0])


def test_simulate_embedding_is_deterministic_and_normalized():
    a = simulate_embedding("a red fox in the forest")
    b = simulate_embedding("a red fox in the forest")
    assert a == b
    assert len(a) == 4096
    norm = math.sqrt(sum(v * v for v in a))
    assert norm == pytest.approx(1.0, rel=1e-6)


def test_simulate_embedding_empty_text_is_stable():
    assert simulate_embedding("") == simulate_embedding("   ")


def test_simulate_embedding_ranks_semantically():
    fox_im = simulate_embedding("red fox in forest")
    fox_post = simulate_embedding("the red fox lives in the forest and hunts")
    wolf_im = simulate_embedding("gray wolf in pack")
    wolf_post = simulate_embedding("the gray wolf lives in a pack and hunts")

    assert cosine_similarity(fox_post, fox_im) > cosine_similarity(fox_post, wolf_im)
    assert cosine_similarity(wolf_post, wolf_im) > cosine_similarity(wolf_post, fox_im)


def test_simulate_embedding_rejects_bad_dim():
    with pytest.raises(ValueError):
        simulate_embedding("x", dim=0)


def test_embed_text_requires_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="No Gemini API key"):
        embed_text("hello world")