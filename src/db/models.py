from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Text,
    DateTime,
    JSON,
    ForeignKey,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class AiCallLog(Base):
    """Record of a single AI call for cost tracking and auditing."""

    __tablename__ = "ai_call_log"

    id = Column(Integer, primary_key=True)
    image_id = Column(Integer, nullable=True)
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
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

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
