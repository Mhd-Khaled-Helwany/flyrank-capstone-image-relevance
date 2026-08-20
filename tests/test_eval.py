import sys
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from db.session import make_engine
from eval_precision import evaluate
from matching.repository import get_post_vectors


def test_eval_precision_on_real_seeded_db():
    """Probe 5: top-1 precision is reported on the labeled set and the guard
    never regresses. Skips unless dev.db is seeded with real Gemini vectors."""
    db = ROOT / "data" / "dev.db"
    if not db.exists():
        pytest.skip("data/dev.db not present")
    engine = make_engine(f"sqlite:///{db}")
    with sessionmaker(bind=engine, expire_on_commit=False)() as s:
        vectors = get_post_vectors(s)
        if not vectors or all(v.model_name == "simulated-embedding" for v in vectors):
            pytest.skip("dev.db not seeded with real Gemini embeddings")

        result = evaluate(s)

        assert result["top1_total"] == 16
        assert result["guard_total"] == 18
        assert result["top1_precision"] >= 0.9
        assert result["guard_precision"] == 1.0
        assert all(row["guard"] == "ok" for row in result["details"])