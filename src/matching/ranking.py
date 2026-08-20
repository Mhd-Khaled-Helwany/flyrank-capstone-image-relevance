from __future__ import annotations
from sqlalchemy.orm import Session
from matching.embeddings import cosine_similarity
from matching.repository import get_image_vectors_with_details, get_post_vector

def rank_images_for_post(session: Session, post_id: int, *, limit: int | None = None) -> list[dict]:
    """Rank every embedded image against a post's stored vector, best first.
    """
    post_vector = get_post_vector(session, post_id)
    if post_vector is None:
        raise ValueError(
            f"No post vector stored for post {post_id} (run scripts/seed_embeddings.py first)"
        )
    return rank_images_for_vector(session, post_vector.embedding, limit=limit)

def rank_images_for_vector(session: Session, query_vector: list[float], *, limit: int | None = None) -> list[dict]:
    """Rank embedded images by cosine similarity to an arbitrary query vector.
    """
    ranked = [
        {
            "image_id": vector.image_id,
            "filename": image.filename,
            "subject": meta.subject,
            "category": meta.category,
            "caption": meta.caption,
            "confidence": meta.confidence,
            "similarity": cosine_similarity(query_vector, vector.embedding),
        }
        for vector, image, meta in get_image_vectors_with_details(session)
    ]
    ranked.sort(key=lambda row: row["similarity"], reverse=True)
    if limit is not None and limit >= 0:
        return ranked[:limit]
    return ranked