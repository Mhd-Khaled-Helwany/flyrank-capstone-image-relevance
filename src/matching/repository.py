from __future__ import annotations
from sqlalchemy.orm import Session
from db.models import Image, ImageMetadata, ImageVector, Post, PostVector

REVIEW_CONFIDENCE_THRESHOLD = 0.75

def upsert_image(
    session: Session,
    *,
    filename: str,
    image_data: bytes | None = None,
    author: str | None = None,
    source_url: str | None = None,
    license: str | None = None,
) -> Image:
    """Insert or update an image row, keyed by filename."""
    row = session.query(Image).filter(Image.filename == filename).one_or_none()
    if row is None:
        row = Image(filename=filename)
        session.add(row)
    row.image_data = image_data
    row.author = author
    row.source_url = source_url
    row.license = license
    session.flush()
    return row

def upsert_post(session: Session, *, title: str, body: str) -> Post:
    """Insert or update a post row, keyed by title."""
    row = session.query(Post).filter(Post.title == title).one_or_none()
    if row is None:
        row = Post(title=title, body=body)
        session.add(row)
    else:
        row.body = body
    session.flush()
    return row

def upsert_image_metadata(
    session: Session,
    *,
    image_id: int,
    category: str,
    subject: str,
    caption: str,
    attributes: list[str] | None = None,
    confidence: float = 0.0,
    model_name: str | None = None,
    model_version: str | None = None,
    raw_response: dict | None = None,
) -> ImageMetadata:
    """Insert or update the single metadata row for an image."""
    row = session.query(ImageMetadata).filter(ImageMetadata.image_id == image_id).one_or_none()
    if row is None:
        row = ImageMetadata(image_id=image_id)
        session.add(row)
    row.category = category
    row.subject = subject
    row.caption = caption
    row.attributes = attributes
    row.confidence = confidence
    row.needs_review = confidence < REVIEW_CONFIDENCE_THRESHOLD
    row.model_name = model_name
    row.model_version = model_version
    row.raw_response = raw_response
    session.flush()
    return row

def upsert_image_vector(session: Session, *, image_id: int, embedding: list[float], model_name: str | None = None) -> ImageVector:
    """Insert or update the single embedding row for an image."""
    row = session.query(ImageVector).filter(ImageVector.image_id == image_id).one_or_none()
    if row is None:
        row = ImageVector(image_id=image_id)
        session.add(row)
    row.embedding = embedding
    row.model_name = model_name
    session.flush()
    return row

def upsert_post_vector(session: Session, *, post_id: int, embedding: list[float], model_name: str | None = None) -> PostVector:
    """Insert or update the single embedding row for a post."""
    row = session.query(PostVector).filter(PostVector.post_id == post_id).one_or_none()
    if row is None:
        row = PostVector(post_id=post_id)
        session.add(row)
    row.embedding = embedding
    row.model_name = model_name
    session.flush()
    return row

def get_image_vector(session: Session, image_id: int) -> ImageVector | None:
    return session.query(ImageVector).filter(ImageVector.image_id == image_id).one_or_none()

def get_post_vector(session: Session, post_id: int) -> PostVector | None:
    return session.query(PostVector).filter(PostVector.post_id == post_id).one_or_none()

def get_image_vectors(session: Session) -> list[ImageVector]:
    return session.query(ImageVector).order_by(ImageVector.image_id).all()

def get_post_vectors(session: Session) -> list[PostVector]:
    return session.query(PostVector).order_by(PostVector.post_id).all()

def list_posts(session: Session) -> list[Post]:
    return session.query(Post).order_by(Post.id).all()

def get_images_with_metadata(session: Session) -> list[tuple[Image, ImageMetadata]]:
    """Return every image that has been tagged, as (image, metadata) pairs."""
    return (
        session.query(Image, ImageMetadata)
        .join(ImageMetadata, ImageMetadata.image_id == Image.id)
        .order_by(Image.id)
        .all()
    )