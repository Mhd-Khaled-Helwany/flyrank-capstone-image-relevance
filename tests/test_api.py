import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from api.dependencies import get_db
from api.main import create_app
from db.models import Base, Image, Post
from seed_embeddings import build_embedder, embed_corpus, seed_corpus


@pytest.fixture()
def api(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as s:
        seed_corpus(s)
        embed, model_name = build_embedder(use_real=False)
        embed_corpus(s, embed, model_name)
        s.commit()

    app = create_app()

    def override_get_db():
        with Session() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), Session


def _post_ids(client):
    return {p["title"]: p["id"] for p in client.get("/posts").json()}


def test_health(api):
    client, _ = api
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["images"] == 50
    assert body["embedded_images"] == 50
    assert body["posts"] == 18
    assert body["embedded_posts"] == 18


def test_list_posts(api):
    client, _ = api
    titles = [p["title"] for p in client.get("/posts").json()]
    assert len(titles) == 18
    assert any("Red Fox" in t for t in titles)


def test_fox_post_images_suggests_fox(api):
    client, _ = api
    fox_id = _post_ids(client)["The Secret Life of the Red Fox"]
    # simulated embeddings sit ~0.15 below the production bar; lower the
    # similarity threshold via the eval/demo knob to exercise the happy path
    body = client.get(f"/posts/{fox_id}/images?similarity_threshold=0.1").json()

    assert body["post_id"] == fox_id
    assert body["result"] == "accepted"
    assert body["reason"] is None
    assert body["suggestion"]["filename"] == "redfox.jpg"
    assert body["suggestion"]["similarity"] > body["ranked"][1]["similarity"]
    assert len(body["ranked"]) == 5
    assert body["ranked"][0]["guard"] == "accepted"
    assert body["ranked"][0]["reason"] is None


def test_chess_post_no_confident_match(api):
    client, _ = api
    chess_id = _post_ids(client)["A Brief History of Chess"]
    body = client.get(f"/posts/{chess_id}/images").json()

    assert body["result"] == "no_confident_match"
    assert body["suggestion"] is None
    assert body["reason"]
    assert all(item["guard"] == "rejected" for item in body["ranked"])


def test_missing_post_returns_404(api):
    client, _ = api
    assert client.get("/posts/99999/images").status_code == 404


def test_post_without_vector_returns_409(api):
    client, Session = api
    with Session() as s:
        post = Post(title="Untagged Post", body="Never embedded")
        s.add(post)
        s.commit()
        post_id = post.id
    response = client.get(f"/posts/{post_id}/images")
    assert response.status_code == 409


def test_image_file_is_served(api):
    client, Session = api
    with Session() as s:
        image = s.query(Image).filter(Image.filename == "redfox.jpg").one()
        image_id = image.id
        payload = image.image_data
    response = client.get(f"/images/{image_id}/file")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content == payload


def test_missing_image_returns_404(api):
    client, _ = api
    assert client.get("/images/99999/file").status_code == 404