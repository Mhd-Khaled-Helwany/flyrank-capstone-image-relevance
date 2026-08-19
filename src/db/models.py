from __future__ import annotations
from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class AiCallLog(Base):
    """Record of a single AI call for cost tracking and auditing."""

    __tablename__ = "ai_call_log"

    id = Column(Integer, primary_key=True)
    image_id = Column(Integer, nullable=True, index=True)
    call_type = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False)
    model_name = Column(String(128), nullable=True)
    model_version = Column(String(128), nullable=True)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    duration_ms = Column(Integer, nullable=False, default=0)
    retry_count = Column(Integer, nullable=False, default=0)
    cost_usd = Column(Float, nullable=False, default=0.0)
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "image_id": self.image_id,
            "call_type": self.call_type,
            "status": self.status,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "duration_ms": self.duration_ms,
            "retry_count": self.retry_count,
            "cost_usd": self.cost_usd,
            "meta": self.meta,
            "created_at": self.created_at.isoformat(),
        }

class Image(Base):
    """One row per image, independent of any AI processing."""

    __tablename__ = "images"

    id = Column(Integer, primary_key=True)
    image_data = Column(LargeBinary, nullable=True)
    filename = Column(String(255), nullable=False)
    author = Column(String(255), nullable=True)
    source_url = Column(String(512), nullable=True)
    license = Column(String(128), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

class Post(Base):
    """One row per blog post — the other half of the matching problem."""

    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)
    title = Column(String(512), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

class ImageMetadata(Base):
    """Validated vision output for a single tagged image."""

    __tablename__ = "image_metadata"
    __table_args__ = (UniqueConstraint("image_id", name="uq_image_metadata_image_id"),)

    id = Column(Integer, primary_key=True)
    image_id = Column(Integer, ForeignKey("images.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(64), nullable=False, index=True)
    subject = Column(String(64), nullable=False, index=True)
    attributes = Column(JSON, nullable=True)
    caption = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False, default=0.0)
    needs_review = Column(Boolean, nullable=False, default=False)
    model_name = Column(String(128), nullable=True)
    model_version = Column(String(128), nullable=True)
    raw_response = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

class ImageVector(Base):
    """Embedding of an image caption, one row per image."""

    __tablename__ = "image_vectors"
    __table_args__ = (UniqueConstraint("image_id", name="uq_image_vectors_image_id"),)

    id = Column(Integer, primary_key=True)
    image_id = Column(Integer, ForeignKey("images.id", ondelete="CASCADE"), nullable=False, index=True)
    embedding = Column(JSON, nullable=False)
    model_name = Column(String(128), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

class PostVector(Base):
    """Embedding of a post's body text, one row per post."""

    __tablename__ = "post_vectors"
    __table_args__ = (UniqueConstraint("post_id", name="uq_post_vectors_post_id"),)

    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    embedding = Column(JSON, nullable=False)
    model_name = Column(String(128), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
