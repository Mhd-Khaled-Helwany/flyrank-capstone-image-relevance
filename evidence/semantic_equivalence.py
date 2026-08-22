"""DoD §6 Matching system #2: "red fox" matches "Vulpes vulpes".

Run: py evidence/semantic_equivalence.py

Part 1 (offline, uses stored vectors): the Red Fox post body names the animal
only as "Vulpes vulpes" in its latin form; no image caption contains any latin
name — yet the stored post vector still ranks redfox.jpg #1 of 50.

Part 2 (two live embedding calls): embeds both phrases and reports their
cosine similarity plus each phrase's best-matching stored caption.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from db.models import ImageVector, Post
from db.session import make_session_factory
from matching.embeddings import cosine_similarity, embed_text
from matching.ranking import rank_images_for_vector


def print_top(ranked: list[dict], label: str) -> None:
    print(f"  {label}")
    for i, row in enumerate(ranked[:3], 1):
        print(f"    {i}. {row['filename']:<14} subject={row['subject']:<10} similarity={row['similarity']:.4f}")


def main() -> None:
    with make_session_factory()() as session:
        post = session.query(Post).filter(Post.title == "The Secret Life of the Red Fox").one()
        sentence = next(s for s in post.body.replace("\n", " ").split(". ") if "Vulpes" in s)
        print(f'post #{post.id} body sentence: "{sentence.strip()}"')

        captions = session.query(ImageVector.image_id).count()
        from db.models import ImageMetadata
        latin_captions = sum(
            1 for (caption,) in session.query(ImageMetadata.caption)
            if "vulpes" in caption.lower() or "lupus" in caption.lower()
        )
        print(f"image captions containing a latin name: {latin_captions}/{captions} "
              f"(zero lexical overlap)")

        post_vec = None  # noqa: F841
        from db.models import PostVector
        pv = session.query(PostVector).filter(PostVector.post_id == post.id).one()
        ranked = rank_images_for_vector(session, pv.embedding)
        print("\n[stored vectors] ranking all images against the post embedding:")
        print_top(ranked, f'best: {ranked[0]["filename"]} -> red fox is rank #1 of {len(ranked)}')

        try:
            common = embed_text("red fox")
            latin = embed_text("Vulpes vulpes")
        except RuntimeError as exc:
            print(f"\n[live embeddings] skipped: {exc}")
            return

        sim = cosine_similarity(common["value"], latin["value"])
        print(f'\n[live embeddings] cosine_similarity(embed("red fox"), embed("Vulpes vulpes")) = {sim:.4f}')
        for label, vec in [("red fox", common), ("Vulpes vulpes", latin)]:
            best = rank_images_for_vector(session, vec["value"])[0]
            print(f'  embed("{label}") best-matches stored caption of '
                  f'{best["filename"]} ({best["subject"]}, sim={best["similarity"]:.4f})')


if __name__ == "__main__":
    main()