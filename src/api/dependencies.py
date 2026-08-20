from __future__ import annotations
from collections.abc import Iterator
from sqlalchemy.orm import Session
from db.session import make_session_factory

_session_factory = make_session_factory()

def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a database session per request."""
    with _session_factory() as session:
        yield session