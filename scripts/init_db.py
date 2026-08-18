"""Tiny helper to create the DB tables for local development.
Run: `.venv/bin/python scripts/init_db.py` from the project root.
"""
from pathlib import Path
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from db.models import Base

def main():
    # Default sqlite file in project root
    url = os.environ.get("DATABASE_URL", "sqlite:///data/dev.db")
    if "::" in url or "sqlite" not in url and "://" not in url:
        # treat as filesystem path
        engine = create_engine(f"sqlite:///{url}", echo=False)
    else:
        engine = create_engine(url, echo=False)
    Base.metadata.create_all(engine)
    print("Created tables (if they did not exist)")

if __name__ == "__main__":
    main()
