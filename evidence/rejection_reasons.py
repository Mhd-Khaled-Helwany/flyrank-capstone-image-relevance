"""DoD §6 Safety layer #2: rejections include a human-readable explanation.

Run: .venv/bin/python evidence/rejection_reasons.py

Forces deliberately wrong (post, image) pairings through the guard and prints
the explanation it produces for each rejection type.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from db.models import Image, Post
from db.session import make_session_factory
from matching.guard import build_candidate, evaluate_candidate

SCENARIOS = [
    ("wrong category: laptop offered to an animal post",
     "The Secret Life of the Red Fox", "laptop.jpg"),
    ("wrong subject: wolf offered to the red-fox post",
     "The Secret Life of the Red Fox", "wolf.jpg"),
    ("untrustworthy tag: basketball.jpg was tagged at 0.3 confidence",
     "The Rise of Running Shoes", "basketball.jpg"),
]


def main() -> None:
    with make_session_factory()() as session:
        for label, post_title, filename in SCENARIOS:
            post = session.query(Post).filter(Post.title == post_title).one()
            image_id = session.query(Image).filter(Image.filename == filename).one().id
            candidate = build_candidate(session, post, image_id)
            verdict = evaluate_candidate(post.body, candidate)
            print(f"{label}")
            print(f"  -> {verdict['result']}: {verdict['reason']}")


if __name__ == "__main__":
    main()