from __future__ import annotations
import mimetypes
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from api.dependencies import get_db
from db.models import Image

router = APIRouter(prefix="/images", tags=["images"])

@router.get("/{image_id}/file")
def get_image_file(image_id: int, db: Session = Depends(get_db)):
    """Serve a stored image BLOB as raw bytes for display in the demo."""
    image = db.get(Image, image_id)
    if image is None or image.image_data is None:
        raise HTTPException(status_code=404, detail=f"Image {image_id} not found")
    media_type = mimetypes.guess_type(image.filename)[0] or "application/octet-stream"
    return Response(content=image.image_data, media_type=media_type)