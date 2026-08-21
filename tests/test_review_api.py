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
from db.models import Base
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


def _materialize(client, post_id):
    # simulated embeddings sit below the production bar; use the eval knob
    return client.post(
        "/review/suggestions",
        json={"post_id": post_id},
        params={"similarity_threshold": 0.1},
    )


def test_materialize_suggestion_is_pending_with_why(api):
    client, _ = api
    fox_id = _post_ids(client)["The Secret Life of the Red Fox"]
    response = _materialize(client, fox_id)

    assert response.status_code == 201
    body = response.json()
    assert body["post_id"] == fox_id
    assert body["status"] == "pending"
    assert body["subject"] == "red fox"
    assert body["why"]["result"] == "accepted"
    assert body["why"]["reason"] is None
    assert body["decisions"] == []


def test_approve_and_reject_recorded_in_trail(api):
    client, _ = api
    ids = _post_ids(client)
    fox = _materialize(client, ids["The Secret Life of the Red Fox"]).json()
    # simulated embeddings rank tiger.jpg top-5 for this post; wolf does not
    tiger = _materialize(client, ids["The Tiger's Vanishing Habitat"]).json()

    approved = client.post(
        f"/review/suggestions/{fox['id']}/decision",
        json={"decision": "approved", "reviewer": "alice"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["decisions"][0]["decision"] == "approved"
    assert approved.json()["decisions"][0]["reviewer"] == "alice"

    rejected = client.post(
        f"/review/suggestions/{tiger['id']}/decision",
        json={"decision": "rejected", "reason": "Wrong tone for the article"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["decisions"][0]["reason"] == "Wrong tone for the article"

    trail = client.get("/review/decisions").json()
    assert [d["decision"] for d in trail] == ["approved", "rejected"]
    assert {d["suggestion_id"] for d in trail} == {fox["id"], tiger["id"]}


def test_materialize_twice_keeps_single_row_and_status(api):
    client, _ = api
    fox_id = _post_ids(client)["The Secret Life of the Red Fox"]
    first = _materialize(client, fox_id).json()
    client.post(
        f"/review/suggestions/{first['id']}/decision",
        json={"decision": "approved"},
    )
    second = _materialize(client, fox_id).json()

    assert second["id"] == first["id"]
    assert second["status"] == "approved"
    rows = client.get("/review/suggestions").json()
    assert len(rows) == 1


def test_inspect_why_endpoint(api):
    client, _ = api
    fox_id = _post_ids(client)["The Secret Life of the Red Fox"]
    suggestion = _materialize(client, fox_id).json()

    detail = client.get(f"/review/suggestions/{suggestion['id']}").json()
    assert detail["why"]["result"] == "accepted"
    assert detail["subject"] == "red fox"
    assert detail["similarity"] > 0


def test_list_suggestions_status_filter(api):
    client, _ = api
    ids = _post_ids(client)
    fox = _materialize(client, ids["The Secret Life of the Red Fox"]).json()
    tiger = _materialize(client, ids["The Tiger's Vanishing Habitat"]).json()
    client.post(f"/review/suggestions/{tiger['id']}/decision", json={"decision": "rejected"})

    pending = client.get("/review/suggestions", params={"status": "pending"}).json()
    assert [s["id"] for s in pending] == [fox["id"]]
    rejected = client.get("/review/suggestions", params={"status": "rejected"}).json()
    assert [s["id"] for s in rejected] == [tiger["id"]]
    assert client.get("/review/suggestions", params={"status": "bogus"}).status_code == 422


def test_no_confident_match_returns_409(api):
    client, _ = api
    chess_id = _post_ids(client)["A Brief History of Chess"]
    response = client.post("/review/suggestions", json={"post_id": chess_id})
    assert response.status_code == 409
    assert "No confident match" in response.json()["detail"]


def test_invalid_decision_value_rejected_422(api):
    client, _ = api
    fox_id = _post_ids(client)["The Secret Life of the Red Fox"]
    suggestion = _materialize(client, fox_id).json()
    response = client.post(
        f"/review/suggestions/{suggestion['id']}/decision",
        json={"decision": "maybe"},
    )
    assert response.status_code == 422


def test_missing_post_and_suggestion_return_404(api):
    client, _ = api
    assert client.post("/review/suggestions", json={"post_id": 99999}).status_code == 404
    assert client.get("/review/suggestions/99999").status_code == 404
    assert (
        client.post("/review/suggestions/99999/decision", json={"decision": "approved"}).status_code
        == 404
    )


def test_post_without_vector_returns_409(api):
    client, Session = api
    from db.models import Post

    with Session() as s:
        post = Post(title="Untagged Post", body="Never embedded")
        s.add(post)
        s.commit()
        post_id = post.id
    response = client.post("/review/suggestions", json={"post_id": post_id})
    assert response.status_code == 409