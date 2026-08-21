from __future__ import annotations
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from fastapi import Depends, FastAPI  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from api.dependencies import get_db  # noqa: E402
from api.routes import images, posts, review  # noqa: E402
from api.schemas import HealthResponse  # noqa: E402
from db.models import Image, Post  # noqa: E402
from matching.repository import get_image_vectors, get_post_vectors  # noqa: E402


def create_app() -> FastAPI:
    app = FastAPI(title="FlyRank Image Relevance API", version="1.0.0")

    app.include_router(posts.router)
    app.include_router(images.router)
    app.include_router(review.router)

    @app.get("/health", response_model=HealthResponse, tags=["ops"])
    def health(db: Session = Depends(get_db)):
        return {
            "status": "ok",
            "images": db.query(Image).count(),
            "embedded_images": len(get_image_vectors(db)),
            "posts": db.query(Post).count(),
            "embedded_posts": len(get_post_vectors(db)),
        }

    return app

app = create_app()