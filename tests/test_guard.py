import csv
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from db.models import Base, Image
from db.session import make_engine
from matching import guard
from matching.guard import (
    ACCEPTED,
    NO_CONFIDENT_MATCH,
    REJECTED,
    build_candidate,
    evaluate_candidate,
    extract_categories,
    extract_subjects,
    suggest_for_post,
)
from matching.repository import get_post_vectors, list_posts
from seed_embeddings import build_embedder, embed_corpus, seed_corpus


def _load_posts():
    with open(ROOT / "data" / "posts.csv", newline="", encoding="utf-8") as f:
        return {row["title"]: row for row in csv.DictReader(f)}


POSTS = _load_posts()


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


def _post_body(title):
    return POSTS[title]["body"]


# --- keyword extraction -----------------------------------------------------

def test_extract_fox_post_keywords():
    body = _post_body("The Secret Life of the Red Fox")
    assert extract_categories(body) == ["animal"]
    assert extract_subjects(body) == ["red fox"]


def test_extract_wolf_post_keywords():
    body = _post_body("Wolves and Pack Behavior")
    assert extract_categories(body) == ["animal"]
    assert extract_subjects(body) == ["wolf"]


def test_extract_lion_post_keywords():
    body = _post_body("Lions of the Serengeti")
    assert extract_categories(body) == ["animal"]
    assert extract_subjects(body) == ["cat"]  # "cats" -> singular "cat"


def test_extract_chess_post_has_no_keywords():
    body = _post_body("A Brief History of Chess")
    assert extract_categories(body) == []
    assert extract_subjects(body) == []


def test_extract_plural_forms():
    assert extract_categories("wild animals and flowering plants") == ["animal", "plant"]
    assert extract_subjects("cats and tigers are apex predators") == ["cat", "tiger"]


def test_keyword_scan_avoids_substring_false_positives():
    assert "hat" not in extract_subjects("howls that can carry for miles")
    assert "owl" not in extract_subjects("howls that can carry for miles")
    assert "car" not in extract_subjects("howls that can carry for miles")
    assert "bed" not in extract_subjects("bedrock is a solid foundation")


# --- evaluate_candidate gates ----------------------------------------------

FOX_TEXT = "A red fox is a wild animal"


def _candidate(**overrides):
    base = {
        "subject": "red fox",
        "category": "animal",
        "confidence": 0.99,
        "similarity": 0.9,
    }
    base.update(overrides)
    return base


def test_category_mismatch_rejected():
    verdict = evaluate_candidate(FOX_TEXT, _candidate(category="furniture"))
    assert verdict == {
        "result": REJECTED,
        "reason": "Category mismatch: expected ['animal'], detected furniture",
    }


def test_empty_category_set_rejects_every_candidate():
    verdict = evaluate_candidate("Chess involves pawns and knights", _candidate())
    assert verdict == {
        "result": REJECTED,
        "reason": "Category mismatch: expected none, detected animal",
    }


def test_subject_mismatch_rejected():
    verdict = evaluate_candidate(FOX_TEXT, _candidate(subject="wolf"))
    assert verdict == {
        "result": REJECTED,
        "reason": "Subject mismatch: expected ['red fox'], detected wolf",
    }


def test_subject_gate_skipped_when_post_names_no_subject():
    text = "The lion is a wild animal living in prides"
    verdict = evaluate_candidate(text, _candidate(subject="tiger"))
    assert verdict["result"] == ACCEPTED  # gate 2 skipped, rest pass


def test_confidence_gate_rejects():
    verdict = evaluate_candidate(FOX_TEXT, _candidate(confidence=0.5))
    assert verdict == {"result": REJECTED, "reason": "Tag confidence too low to trust"}


def test_similarity_gate_rejects():
    verdict = evaluate_candidate(FOX_TEXT, _candidate(similarity=0.5))
    assert verdict == {"result": REJECTED, "reason": "Similarity below threshold"}


def test_all_gates_pass_accepted():
    verdict = evaluate_candidate(FOX_TEXT, _candidate())
    assert verdict == {"result": ACCEPTED, "reason": None}


# --- suggest_for_post walk --------------------------------------------------

class _FakePost:
    def __init__(self, body, id=1):
        self.body = body
        self.id = id


def _rank(rows):
    def fake(session, post_id, *, limit=None):
        return rows[:limit] if limit else rows

    return fake


def test_walk_skips_rejected_and_takes_first_accepted(monkeypatch):
    rows = [
        {"subject": "red fox", "category": "animal", "confidence": 0.99, "similarity": 0.5, "filename": "a.jpg"},
        {"subject": "red fox", "category": "animal", "confidence": 0.99, "similarity": 0.9, "filename": "b.jpg"},
    ]
    monkeypatch.setattr(guard, "rank_images_for_post", _rank(rows))
    result = suggest_for_post(None, _FakePost(FOX_TEXT))
    assert result["result"] == ACCEPTED
    assert result["image"]["filename"] == "b.jpg"


def test_walk_all_rejected_yields_no_confident_match(monkeypatch):
    rows = [
        {"subject": "red fox", "category": "animal", "confidence": 0.99, "similarity": 0.5, "filename": "a.jpg"},
        {"subject": "red fox", "category": "animal", "confidence": 0.99, "similarity": 0.4, "filename": "b.jpg"},
    ]
    monkeypatch.setattr(guard, "rank_images_for_post", _rank(rows))
    result = suggest_for_post(None, _FakePost(FOX_TEXT))
    assert result == {
        "result": NO_CONFIDENT_MATCH,
        "reason": "Similarity below threshold",
    }


def test_walk_empty_ranked_list(monkeypatch):
    monkeypatch.setattr(guard, "rank_images_for_post", _rank([]))
    result = suggest_for_post(None, _FakePost(FOX_TEXT))
    assert result == {"result": NO_CONFIDENT_MATCH, "reason": "No embedded images to rank"}


# --- end-to-end on simulated (in-memory) embeddings ------------------------

def test_forced_wolf_candidate_rejected_on_fox_post(session):
    seed_corpus(session)
    _embed_all(session)
    fox = next(p for p in list_posts(session) if "Red Fox" in p.title)
    wolf_id = session.query(Image).filter(Image.filename == "wolf.jpg").one().id

    candidate = build_candidate(session, fox, wolf_id)
    verdict = evaluate_candidate(fox.body, candidate)

    assert candidate["subject"] == "wolf"
    assert verdict["result"] == REJECTED
    assert "Subject mismatch" in verdict["reason"]
    assert "red fox" in verdict["reason"]
    assert "wolf" in verdict["reason"]


def test_fox_post_walk_accepts_fox_on_simulated_data(session):
    seed_corpus(session)
    _embed_all(session)
    fox = next(p for p in list_posts(session) if "Red Fox" in p.title)

    result = suggest_for_post(session, fox, similarity_threshold=0.1)

    assert result["result"] == ACCEPTED
    assert result["image"]["filename"] == "redfox.jpg"


# --- integration against the real seeded dev.db (skips if not present) -----

def test_real_guard_on_seeded_db():
    db = ROOT / "data" / "dev.db"
    if not db.exists():
        pytest.skip("data/dev.db not present")
    engine = make_engine(f"sqlite:///{db}")
    with sessionmaker(bind=engine, expire_on_commit=False)() as s:
        vectors = get_post_vectors(s)
        if not vectors or all(v.model_name == "simulated-embedding" for v in vectors):
            pytest.skip("dev.db not seeded with real Gemini embeddings")

        posts = {p.title: p for p in list_posts(s)}

        fox = posts["The Secret Life of the Red Fox"]
        fox_suggestion = suggest_for_post(s, fox)
        assert fox_suggestion["result"] == ACCEPTED
        assert fox_suggestion["image"]["filename"] == "redfox.jpg"

        wolf_id = s.query(Image).filter(Image.filename == "wolf.jpg").one().id
        wolf_verdict = evaluate_candidate(fox.body, build_candidate(s, fox, wolf_id))
        assert wolf_verdict["result"] == REJECTED
        assert "Subject mismatch" in wolf_verdict["reason"]

        for title, row in POSTS.items():
            post = posts[title]
            suggestion = suggest_for_post(s, post)
            if row["expected_result"] == "accepted":
                assert suggestion["result"] == ACCEPTED, title
                assert suggestion["image"]["subject"] == row["expected_subject"], title
            else:
                assert suggestion["result"] == NO_CONFIDENT_MATCH, title