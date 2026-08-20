import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from db.models import Base
from matching.embeddings import simulate_embedding
from matching.ranking import rank_images_for_post, rank_images_for_vector
from matching.repository import list_posts, upsert_post
from seed_embeddings import build_embedder, embed_corpus, seed_corpus


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as s:
        seed_corpus(s)
        embed, _ = build_embedder(use_real=False)
        embed_corpus(s, embed, "simulated-embedding")
        yield s


def _fox_post(session):
    return next(p for p in list_posts(session) if "Red Fox" in p.title)


def test_fox_post_ranks_fox_image_first(session):
    ranked = rank_images_for_post(session, _fox_post(session).id)
    assert ranked[0]["filename"] == "redfox.jpg"


def test_ranking_is_sorted_descending(session):
    ranked = rank_images_for_post(session, _fox_post(session).id)
    sims = [row["similarity"] for row in ranked]
    assert sims == sorted(sims, reverse=True)
    assert len(ranked) == 50


def test_ranking_results_carry_metadata(session):
    top = rank_images_for_post(session, _fox_post(session).id)[0]
    assert {"image_id", "filename", "subject", "category", "caption", "confidence", "similarity"} <= set(top)
    assert top["subject"] == "red fox"
    assert top["category"] == "animal"
    assert 0.0 <= top["confidence"] <= 1.0


def test_ranking_limit(session):
    ranked = rank_images_for_post(session, _fox_post(session).id, limit=5)
    assert len(ranked) == 5
    assert ranked[0]["filename"] == "redfox.jpg"


def test_rank_for_arbitrary_query_vector(session):
    fox_like = simulate_embedding("red fox")
    ranked = rank_images_for_vector(session, fox_like)
    assert ranked[0]["filename"] == "redfox.jpg"


def test_ranking_requires_stored_post_vector(session):
    orphan = upsert_post(session, title="Never embedded", body="plain text")
    session.flush()
    with pytest.raises(ValueError, match="No post vector stored"):
        rank_images_for_post(session, orphan.id)