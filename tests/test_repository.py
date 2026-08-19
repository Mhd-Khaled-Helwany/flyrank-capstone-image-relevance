import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from db.models import Base, Image, ImageMetadata, ImageVector, Post, PostVector
from matching.repository import (
    get_image_vector,
    get_images_with_metadata,
    get_post_vector,
    list_posts,
    upsert_image,
    upsert_image_metadata,
    upsert_image_vector,
    upsert_post,
    upsert_post_vector,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as s:
        yield s


def test_upsert_image_creates_and_updates(session):
    img = upsert_image(session, filename="redfox.jpg", author="Ray Hennessy")
    session.flush()
    assert img.id is not None
    assert img.filename == "redfox.jpg"

    upsert_image(session, filename="redfox.jpg", author="Updated")
    session.flush()
    assert session.query(Image).count() == 1
    assert session.query(Image).one().author == "Updated"


def test_upsert_post_creates_and_updates(session):
    post = upsert_post(session, title="The Red Fox", body="Foxes are wild animals.")
    session.flush()
    assert post.id is not None
    assert session.query(Post).count() == 1

    upsert_post(session, title="The Red Fox", body="Updated body.")
    session.flush()
    assert session.query(Post).count() == 1
    assert session.query(Post).one().body == "Updated body."


def test_metadata_sets_needs_review_from_confidence(session):
    img = upsert_image(session, filename="redfox.jpg")
    session.flush()

    low = upsert_image_metadata(session, image_id=img.id, category="animal", subject="red fox", caption="c", confidence=0.5)
    assert low.needs_review is True

    high = upsert_image_metadata(session, image_id=img.id, category="animal", subject="red fox", caption="c", confidence=0.9)
    assert high.needs_review is False
    assert session.query(ImageMetadata).count() == 1  # upserted, not duplicated


def test_image_vector_round_trip_and_upsert(session):
    img = upsert_image(session, filename="redfox.jpg")
    session.flush()

    vec = [0.1, 0.2, 0.3]
    upsert_image_vector(session, image_id=img.id, embedding=vec, model_name="m")
    session.flush()

    stored = get_image_vector(session, img.id)
    assert stored is not None
    assert stored.embedding == vec
    assert stored.model_name == "m"

    upsert_image_vector(session, image_id=img.id, embedding=[0.9, 0.8, 0.7])
    session.flush()
    assert session.query(ImageVector).count() == 1  # still one row
    assert get_image_vector(session, img.id).embedding == [0.9, 0.8, 0.7]


def test_post_vector_round_trip(session):
    post = upsert_post(session, title="T", body="b")
    session.flush()

    upsert_post_vector(session, post_id=post.id, embedding=[1.0, 2.0])
    session.flush()

    stored = get_post_vector(session, post.id)
    assert stored is not None
    assert stored.embedding == [1.0, 2.0]


def test_get_images_with_metadata_joins(session):
    img = upsert_image(session, filename="redfox.jpg")
    session.flush()
    upsert_image_metadata(session, image_id=img.id, category="animal", subject="red fox", caption="A fox.")
    session.flush()

    pairs = get_images_with_metadata(session)
    assert len(pairs) == 1
    image, meta = pairs[0]
    assert image.filename == "redfox.jpg"
    assert meta.subject == "red fox"


def test_list_posts_orders_by_id(session):
    upsert_post(session, title="B", body="1")
    upsert_post(session, title="A", body="2")
    session.flush()
    posts = list_posts(session)
    assert [p.title for p in posts] == ["B", "A"]