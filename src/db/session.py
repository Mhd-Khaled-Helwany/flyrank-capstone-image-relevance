from __future__ import annotations
import os
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

def get_database_url() -> str:
    """Single source of truth for the DB URL: the DATABASE_URL env var."""
    return os.environ.get("DATABASE_URL", "sqlite:///./data/dev.db")

def make_engine(url: str | None = None) -> Engine:
    return create_engine(url or get_database_url())

def make_session_factory(engine: Engine | None = None) -> sessionmaker:
    """Build a session factory bound to the configured engine."""
    return sessionmaker(bind=engine or make_engine(), expire_on_commit=False)