"""DoD §6 Matching system #1: embeddings stored; posts return ranked images.

Run: py evidence/ranked_suggestions.py

Reads the seeded dev.db and shows (a) the stored embedding counts per model,
(b) the full ranked candidate list for the Red Fox post, exactly what
GET /posts/{id}/images serves.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from db.models import ImageVector, PostVector
from db.session import make_session_factory
from matching.guard import GUARD_TOP_N
from matching.ranking import rank_images_for_post


def main() -> None:
    with make_session_factory()() as session:
        image_vecs = session.query(ImageVector).all()
        post_vecs = session.query(PostVector).all()
        image_models = sorted({v.model_name for v in image_vecs})
        post_models = sorted({v.model_name for v in post_vecs})
        print(f"stored embeddings: {len(image_vecs)} image_vectors {image_models}, "
              f"{len(post_vecs)} post_vectors {post_models}")

        from db.models import Post
        post = session.query(Post).filter(Post.title == "The Secret Life of the Red Fox").one()

        ranked = rank_images_for_post(session, post.id, limit=GUARD_TOP_N)
        print(f'\npost #{post.id} "{post.title}" - top {len(ranked)} ranked images:')
        for i, row in enumerate(ranked, 1):
            print(f"  {i}. {row['filename']:<14} subject={row['subject']:<10} "
                  f"category={row['category']:<18} similarity={row['similarity']:.4f}")


if __name__ == "__main__":
    main()