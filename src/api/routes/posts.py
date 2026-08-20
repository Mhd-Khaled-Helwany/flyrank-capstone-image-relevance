from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from api.dependencies import get_db
from api.schemas import PostImagesResponse, PostSummary, RankedCandidate, Suggestion
from db.models import Post
from matching import guard as guard_mod
from matching.ranking import rank_images_for_post
from matching.repository import list_posts

router = APIRouter(prefix="/posts", tags=["posts"])

@router.get("", response_model=list[PostSummary])
def list_post_summaries(db: Session = Depends(get_db)):
    return [{"id": p.id, "title": p.title} for p in list_posts(db)]

@router.get("/{post_id}/images", response_model=PostImagesResponse)
def get_post_images(
    post_id: int,
    similarity_threshold: float | None = None,
    confidence_threshold: float | None = None,
    db: Session = Depends(get_db),
):
    """Rank every embedded image for a post and walk the mismatch guard.

    Mirrors the architecture overview: similarity ranking -> mismatch guard ->
    suggested image (explained) or "no good match" with reasons.

    `similarity_threshold` / `confidence_threshold` are optional eval/demo knobs
    that override the guard's defaults (docs/matching.md §3, retuned from eval
    data in Phase 4).
    """
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail=f"Post {post_id} not found")

    try:
        ranked = rank_images_for_post(db, post_id, limit=guard_mod.GUARD_TOP_N)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    walk = guard_mod.walk_candidates(
        post.body,
        ranked,
        similarity_threshold=(
            similarity_threshold
            if similarity_threshold is not None
            else guard_mod.SIMILARITY_THRESHOLD
        ),
        confidence_threshold=(
            confidence_threshold
            if confidence_threshold is not None
            else guard_mod.REVIEW_CONFIDENCE_THRESHOLD
        ),
    )

    return {
        "post_id": post.id,
        "title": post.title,
        "result": walk["result"],
        "reason": walk["reason"],
        "suggestion": Suggestion(**walk["suggestion"]) if walk["suggestion"] else None,
        "ranked": [
            RankedCandidate(
                image_id=row["image_id"],
                filename=row["filename"],
                subject=row["subject"],
                category=row["category"],
                caption=row["caption"],
                similarity=row["similarity"],
                guard=verdict["result"],
                reason=verdict["reason"],
            )
            for row, verdict in zip(ranked, walk["verdicts"])
        ],
    }