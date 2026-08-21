from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from api.dependencies import get_db
from api.schemas import (
    DecisionCreate,
    DecisionOut,
    GuardVerdict,
    SuggestionCreate,
    SuggestionDetail,
    SuggestionOut,
)
from db.models import Post, Suggestion
from matching import guard as guard_mod
from matching.repository import (
    get_suggestion,
    list_decisions,
    list_suggestions,
    record_decision,
    upsert_suggestion,
)

router = APIRouter(prefix="/review", tags=["review"])

def _detail(db: Session, suggestion: Suggestion) -> dict:
    """Build the inspect-why view: fresh guard verdict + decision trail.
    """
    post = db.get(Post, suggestion.post_id)
    if post is None:
        raise HTTPException(status_code=404, detail=f"Post {suggestion.post_id} not found")
    try:
        candidate = guard_mod.build_candidate(db, post, suggestion.image_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    verdict = guard_mod.evaluate_candidate(
        post.body,
        candidate,
        similarity_threshold=(
            suggestion.similarity_threshold
            if suggestion.similarity_threshold is not None
            else guard_mod.SIMILARITY_THRESHOLD
        ),
        confidence_threshold=(
            suggestion.confidence_threshold
            if suggestion.confidence_threshold is not None
            else guard_mod.REVIEW_CONFIDENCE_THRESHOLD
        ),
    )
    return {
        "id": suggestion.id,
        "post_id": suggestion.post_id,
        "image_id": suggestion.image_id,
        "status": suggestion.status,
        "similarity": suggestion.similarity,
        "confidence": suggestion.confidence,
        "subject": suggestion.subject,
        "category": suggestion.category,
        "caption": suggestion.caption,
        "why": verdict,
        "decisions": [
            {
                "id": d.id,
                "suggestion_id": d.suggestion_id,
                "decision": d.decision,
                "reason": d.reason,
                "reviewer": d.reviewer,
            }
            for d in list_decisions(db, suggestion.id)
        ],
    }

@router.post("/suggestions", response_model=SuggestionDetail, status_code=201)
def materialize_suggestion(
    payload: SuggestionCreate,
    similarity_threshold: float | None = None,
    confidence_threshold: float | None = None,
    db: Session = Depends(get_db),
):
    """Run the matching flow for a post and persist its suggested pairing
    as a pending row for human review.

    `similarity_threshold` / `confidence_threshold` are optional eval/demo
    knobs mirroring GET /posts/{id}/images.
    """
    post = db.get(Post, payload.post_id)
    if post is None:
        raise HTTPException(status_code=404, detail=f"Post {payload.post_id} not found")

    try:
        result = guard_mod.suggest_for_post(
            db,
            post,
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
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    if result["result"] != guard_mod.ACCEPTED or result["image"] is None:
        raise HTTPException(
            status_code=409,
            detail=f"No confident match to review: {result['reason']}",
        )

    suggestion = upsert_suggestion(
        db,
        post_id=post.id,
        candidate=result["image"],
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
    db.commit()
    db.refresh(suggestion)
    return _detail(db, suggestion)

@router.get("/suggestions", response_model=list[SuggestionOut])
def list_review_suggestions(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """The review admin table; optionally filtered by status."""
    if status is not None and status not in (
        Suggestion.PENDING,
        Suggestion.APPROVED,
        Suggestion.REJECTED,
    ):
        raise HTTPException(
            status_code=422,
            detail=f"status must be one of pending, approved, rejected (got '{status}')",
        )
    return [
        {
            "id": s.id,
            "post_id": s.post_id,
            "image_id": s.image_id,
            "status": s.status,
            "similarity": s.similarity,
            "confidence": s.confidence,
            "subject": s.subject,
            "category": s.category,
            "caption": s.caption,
        }
        for s in list_suggestions(db, status)
    ]


@router.get("/suggestions/{suggestion_id}", response_model=SuggestionDetail)
def get_review_suggestion(suggestion_id: int, db: Session = Depends(get_db)):
    """Inspect a suggestion: why this image was selected, plus its trail."""
    suggestion = get_suggestion(db, suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail=f"Suggestion {suggestion_id} not found")
    return _detail(db, suggestion)

@router.post("/suggestions/{suggestion_id}/decision", response_model=SuggestionDetail)
def decide_suggestion(
    suggestion_id: int,
    payload: DecisionCreate,
    db: Session = Depends(get_db),
):
    """Approve or reject a suggested pairing; appends to the review trail."""
    suggestion = get_suggestion(db, suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail=f"Suggestion {suggestion_id} not found")
    record_decision(
        db,
        suggestion_id=suggestion.id,
        decision=payload.decision,
        reason=payload.reason,
        reviewer=payload.reviewer,
    )
    db.commit()
    db.refresh(suggestion)
    return _detail(db, suggestion)

@router.get("/decisions", response_model=list[DecisionOut])
def list_review_decisions(db: Session = Depends(get_db)):
    """The full append-only review trail, oldest first."""
    return [
        {
            "id": d.id,
            "suggestion_id": d.suggestion_id,
            "decision": d.decision,
            "reason": d.reason,
            "reviewer": d.reviewer,
        }
        for d in list_decisions(db)
    ]