from __future__ import annotations
import re
from sqlalchemy.orm import Session
from db.models import Image, ImageMetadata, Post
from matching.embeddings import cosine_similarity
from matching.ranking import rank_images_for_post
from matching.repository import (
    REVIEW_CONFIDENCE_THRESHOLD,
    get_image_vector,
    get_post_vector,
)
from vision.schema import Category, Subject

ACCEPTED = "accepted"
REJECTED = "rejected"
NO_CONFIDENT_MATCH = "no_confident_match"

# How far down the ranked list the guard walks before giving up (§1).
GUARD_TOP_N = 5

SIMILARITY_THRESHOLD = 0.74

def _keyword_pattern(value: str) -> re.Pattern:
    """Word-boundary keyword pattern with an optional plural 's'.
    """
    return re.compile(rf"\b{re.escape(value)}s?\b")

def extract_categories(text: str) -> list[str]:
    """Categories from the category enum mentioned in the post text."""
    lowered = text.lower()
    return [m.value for m in Category if _keyword_pattern(m.value).search(lowered)]

def extract_subjects(text: str) -> list[str]:
    """Subjects from the subject enum mentioned in the post text."""
    lowered = text.lower()
    return [m.value for m in Subject if _keyword_pattern(m.value).search(lowered)]

def evaluate_candidate(
    post_text: str,
    candidate: dict,
    *,
    similarity_threshold: float = SIMILARITY_THRESHOLD,
    confidence_threshold: float = REVIEW_CONFIDENCE_THRESHOLD,
) -> dict:
    """Pure guard check for a single (post, image) pair.

    `candidate` is a ranking row dict with keys `subject`, `category`,
    `confidence`, and `similarity`. Returns `{"result": "accepted"|"rejected",
    "reason": str|None}` — the single source of explanation used by the
    ranking walk and the review API's "inspect why" endpoint.
    """
    categories = extract_categories(post_text)
    if not categories:
        return {
            "result": REJECTED,
            "reason": f"Category mismatch: expected none, detected {candidate['category']}",
        }
    if candidate["category"] not in categories:
        return {
            "result": REJECTED,
            "reason": f"Category mismatch: expected {sorted(categories)}, detected {candidate['category']}",
        }

    subjects = extract_subjects(post_text)
    if subjects and candidate["subject"] not in subjects:
        return {
            "result": REJECTED,
            "reason": f"Subject mismatch: expected {sorted(subjects)}, detected {candidate['subject']}",
        }

    if candidate["confidence"] < confidence_threshold:
        return {"result": REJECTED, "reason": "Tag confidence too low to trust"}

    if candidate["similarity"] < similarity_threshold:
        return {"result": REJECTED, "reason": "Similarity below threshold"}

    return {"result": ACCEPTED, "reason": None}

def build_candidate(session: Session, post: Post, image_id: int) -> dict:
    """Build the candidate dict for a specific (post, image) pair.
    """
    post_vector = get_post_vector(session, post.id)
    if post_vector is None:
        raise ValueError(f"No post vector stored for post {post.id}")
    image_vector = get_image_vector(session, image_id)
    if image_vector is None:
        raise ValueError(f"No image vector stored for image {image_id}")

    image = session.get(Image, image_id)
    meta = session.query(ImageMetadata).filter(ImageMetadata.image_id == image_id).one_or_none()
    if image is None or meta is None:
        raise ValueError(f"No tagged image {image_id}")

    return {
        "image_id": image_id,
        "filename": image.filename,
        "subject": meta.subject,
        "category": meta.category,
        "caption": meta.caption,
        "confidence": meta.confidence,
        "similarity": cosine_similarity(post_vector.embedding, image_vector.embedding),
    }

def suggest_for_post(
    session: Session,
    post: Post,
    *,
    top_n: int = GUARD_TOP_N,
    similarity_threshold: float = SIMILARITY_THRESHOLD,
    confidence_threshold: float = REVIEW_CONFIDENCE_THRESHOLD,
) -> dict:
    """Full matching flow (§1): rank, walk the top-N through the guard.

    Returns the first ACCEPTED candidate as the suggestion, or
    `no_confident_match` with the top-ranked candidate's rejection reason.
    """
    ranked = rank_images_for_post(session, post.id, limit=top_n)
    for candidate in ranked:
        verdict = evaluate_candidate(
            post.body,
            candidate,
            similarity_threshold=similarity_threshold,
            confidence_threshold=confidence_threshold,
        )
        if verdict["result"] == ACCEPTED:
            return {"result": ACCEPTED, "image": candidate, "reason": None}

    if not ranked:
        return {"result": NO_CONFIDENT_MATCH, "reason": "No embedded images to rank"}

    reason = evaluate_candidate(
        post.body,
        ranked[0],
        similarity_threshold=similarity_threshold,
        confidence_threshold=confidence_threshold,
    )["reason"]
    return {"result": NO_CONFIDENT_MATCH, "reason": reason}