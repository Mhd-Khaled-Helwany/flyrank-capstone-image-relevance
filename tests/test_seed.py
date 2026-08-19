import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from db.models import Base, Image
from matching.embeddings import cosine_similarity
from matching.repository import (
    get_image_vector,
    get_image_vectors,
    get_post_vector,
    list_posts,
)
from seed_embeddings import build_embedder, embed_corpus, seed_corpus


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as s:
        yield s


def _embed_all(session):
    embed, model_name = build_embedder(use_real=False)
    return embed_corpus(session, embed, model_name)


def test_seed_embeds_every_image_and_post(session):
    seed_corpus(session)
    image_count, post_count = _embed_all(session)
    assert image_count == 50
    assert post_count == 18
    assert len(get_image_vectors(session)) == 50
    assert len(list_posts(session)) == 18
    assert all(len(v.embedding) == 4096 for v in get_image_vectors(session))


def test_fox_post_ranks_fox_image_first(session):
    seed_corpus(session)
    _embed_all(session)

    fox_post = next(p for p in list_posts(session) if "Red Fox" in p.title)
    fox_vec = get_post_vector(session, fox_post.id).embedding

    best = max(get_image_vectors(session), key=lambda iv: cosine_similarity(fox_vec, iv.embedding))
    filename = session.query(Image).filter(Image.id == best.image_id).one().filename
    assert filename == "redfox.jpg"


def test_captions_produce_non_empty_embeddings(session):
    seed_corpus(session)
    _embed_all(session)
    for v in get_image_vectors(session):
        assert v.embedding
        assert any(x != 0.0 for x in v.embedding)


def test_embedding_is_idempotent(session):
    seed_corpus(session)
    first, _ = _embed_all(session)
    second, _ = _embed_all(session)  # running again must not duplicate rows
    assert first == second == 50
    assert len(get_image_vectors(session)) == 50
    fox_post = next(p for p in list_posts(session) if "Red Fox" in p.title)
    assert get_post_vector(session, fox_post.id) is not None