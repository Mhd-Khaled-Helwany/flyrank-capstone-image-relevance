from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel

class RankedCandidate(BaseModel):
    """One entry in the ranked list returned by GET /posts/{id}/images."""

    image_id: int
    filename: str
    subject: str
    category: str
    caption: str
    similarity: float
    guard: str
    reason: Optional[str] = None

class Suggestion(BaseModel):
    """The accepted image for a post, if the guard found one."""

    image_id: int
    filename: str
    subject: str
    category: str
    caption: str
    confidence: float
    similarity: float

class PostImagesResponse(BaseModel):
    """Response for GET /posts/{id}/images — the ranked walk + suggestion."""

    post_id: int
    title: str
    result: str
    reason: Optional[str] = None
    suggestion: Optional[Suggestion] = None
    ranked: list[RankedCandidate]

class PostSummary(BaseModel):
    id: int
    title: str

class HealthResponse(BaseModel):
    status: str
    images: int
    embedded_images: int
    posts: int
    embedded_posts: int

class SuggestionCreate(BaseModel):
    """Request body for POST /review/suggestions — materialize a post's suggestion."""

    post_id: int

class DecisionCreate(BaseModel):
    """Request body for POST /review/suggestions/{id}/decision."""

    decision: Literal["approved", "rejected"]
    reason: Optional[str] = None
    reviewer: Optional[str] = None

class DecisionOut(BaseModel):
    """One entry in the review trail."""

    id: int
    suggestion_id: int
    decision: str
    reason: Optional[str] = None
    reviewer: Optional[str] = None

class GuardVerdict(BaseModel):
    """The guard's fresh verdict for a suggested pair — why it was selected."""

    result: str
    reason: Optional[str] = None

class SuggestionOut(BaseModel):
    """One row of the review admin table."""

    id: int
    post_id: int
    image_id: int
    status: str
    similarity: float
    confidence: float
    subject: str
    category: str
    caption: str

class SuggestionDetail(SuggestionOut):
    """Suggestion plus the inspect-why verdict and its decision trail."""

    why: GuardVerdict
    decisions: list[DecisionOut] = []