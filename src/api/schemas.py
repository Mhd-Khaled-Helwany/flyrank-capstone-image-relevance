from __future__ import annotations
from typing import Optional
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